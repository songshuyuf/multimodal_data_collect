"""
客户端更新 API
==============
GET  /update/check          → 客户端查询是否有新版本（无需认证）
POST /update/release        → 管理员发布新版本（需认证 + 上传安装包）
GET  /update/releases       → 列出所有版本
GET  /update/download/{ver} → 下载指定版本安装包
"""

import hashlib
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from packaging.version import Version

from app.core.database import get_db
from app.core.config import settings
from app.api.deps import get_org_id
from app.models import AppRelease
from app.schemas.schemas import (
    UpdateCheckResponse, ReleaseCreateRequest, ReleaseResponse,
)
from app.services.storage import StorageService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/update", tags=["update"])

RELEASE_BUCKET_PREFIX = "releases"

_storage: Optional[StorageService] = None


def _get_storage() -> StorageService:
    global _storage
    if _storage is None:
        _storage = StorageService()
    return _storage


@router.get("/check", response_model=UpdateCheckResponse)
async def check_update(
    version: str = Query("0.0.0", description="客户端当前版本号"),
    platform: str = Query("windows", description="平台"),
    db: AsyncSession = Depends(get_db),
):
    """
    客户端启动时调用，无需认证。
    比较客户端版本与服务端最新发布版本，返回更新信息。
    """
    stmt = (
        select(AppRelease)
        .where(AppRelease.platform == platform, AppRelease.is_active == True)
        .order_by(desc(AppRelease.created_at))
        .limit(1)
    )
    result = await db.execute(stmt)
    latest = result.scalar_one_or_none()

    if latest is None:
        return UpdateCheckResponse(update_available=False)

    try:
        has_update = Version(latest.version) > Version(version)
    except Exception:
        has_update = latest.version != version

    if not has_update:
        return UpdateCheckResponse(
            update_available=False,
            latest_version=latest.version,
        )

    server_host = settings.SERVER_HOST if hasattr(settings, 'SERVER_HOST') else "172.16.55.196:8000"
    download_url = f"http://{server_host}/api/v1/update/download/{latest.version}"

    return UpdateCheckResponse(
        update_available=True,
        latest_version=latest.version,
        download_url=download_url,
        release_notes=latest.release_notes or "",
        file_size=latest.file_size or 0,
        file_hash=latest.file_hash or "",
        mandatory=latest.mandatory,
    )


@router.post("/release", response_model=ReleaseResponse)
async def create_release(
    version: str = Form(...),
    platform: str = Form("windows"),
    release_notes: str = Form(""),
    mandatory: bool = Form(False),
    installer: UploadFile = File(..., description="安装包 .exe 文件"),
    org_id=Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    """
    管理员上传新版本安装包到 MinIO 并创建版本记录。
    需要 API Key 认证。
    """
    existing = await db.execute(
        select(AppRelease).where(
            AppRelease.version == version,
            AppRelease.platform == platform,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"版本 {version} ({platform}) 已存在")

    content = await installer.read()
    file_size = len(content)
    file_hash = hashlib.md5(content).hexdigest()

    minio_key = f"{RELEASE_BUCKET_PREFIX}/{platform}/{version}/{installer.filename}"

    storage = _get_storage()
    ok = storage.put_object(minio_key, content, content_type="application/octet-stream")
    if not ok:
        raise HTTPException(status_code=500, detail="上传安装包到存储失败")

    release = AppRelease(
        version=version,
        platform=platform,
        file_name=installer.filename,
        file_size=file_size,
        file_hash=file_hash,
        minio_key=minio_key,
        release_notes=release_notes,
        mandatory=mandatory,
    )
    db.add(release)
    await db.commit()
    await db.refresh(release)

    logger.info("新版本已发布: %s (%s) - %s bytes", version, platform, file_size)
    return release


@router.get("/releases")
async def list_releases(
    platform: str = Query("windows"),
    db: AsyncSession = Depends(get_db),
):
    """列出所有版本（最新在前）。"""
    stmt = (
        select(AppRelease)
        .where(AppRelease.platform == platform)
        .order_by(desc(AppRelease.created_at))
    )
    result = await db.execute(stmt)
    releases = result.scalars().all()
    return [ReleaseResponse.model_validate(r) for r in releases]


@router.get("/download/{version}")
async def download_release(
    version: str,
    platform: str = Query("windows"),
    db: AsyncSession = Depends(get_db),
):
    """下载指定版本的安装包。"""
    stmt = select(AppRelease).where(
        AppRelease.version == version,
        AppRelease.platform == platform,
        AppRelease.is_active == True,
    )
    result = await db.execute(stmt)
    release = result.scalar_one_or_none()

    if release is None:
        raise HTTPException(status_code=404, detail=f"版本 {version} 不存在")

    storage = _get_storage()
    data = storage.get_object(release.minio_key)
    if data is None:
        raise HTTPException(status_code=500, detail="存储中未找到安装包文件")

    import io
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{release.file_name}"',
            "Content-Length": str(release.file_size),
        },
    )
