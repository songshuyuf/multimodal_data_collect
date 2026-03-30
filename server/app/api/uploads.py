"""
分块上传 API — 与客户端 UploadManager 对接
===========================================
POST   /uploads/init                    → 初始化上传
PUT    /uploads/{upload_id}/chunks/{i}  → 上传分块
POST   /uploads/{upload_id}/complete    → 完成确认
GET    /uploads/{upload_id}/status      → 查询状态
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_org_id
from app.schemas.schemas import (
    UploadInitRequest, UploadInitResponse,
    UploadStatusResponse, UploadCompleteResponse,
)
from app.services.upload_service import UploadService

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/init", response_model=UploadInitResponse)
async def init_upload(
    body: UploadInitRequest,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    upload_id, uploaded_chunks = await UploadService.init_upload(
        db=db,
        org_id=org_id,
        session_name=body.session_name,
        file_name=body.file_name,
        modality=body.modality,
        file_size=body.file_size,
        file_hash=body.file_hash,
        total_chunks=body.total_chunks,
        compressed=body.compressed,
    )
    return UploadInitResponse(upload_id=upload_id, uploaded_chunks=uploaded_chunks)


@router.put("/{upload_id}/chunks/{chunk_index}")
async def upload_chunk(
    upload_id: UUID,
    chunk_index: int,
    request: Request,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="空分块")

    ok = await UploadService.receive_chunk(db, upload_id, chunk_index, body)
    if not ok:
        raise HTTPException(status_code=400, detail="分块写入失败")

    return {"status": "ok", "chunk_index": chunk_index, "size": len(body)}


@router.post("/{upload_id}/complete", response_model=UploadCompleteResponse)
async def complete_upload(
    upload_id: UUID,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    data_file = await UploadService.complete_upload(db, upload_id, org_id)
    if not data_file:
        raise HTTPException(status_code=400, detail="完成失败：分块不完整或上传不存在")

    return UploadCompleteResponse(
        data_file_id=data_file.id,
        minio_key=data_file.minio_key,
    )


@router.get("/{upload_id}/status", response_model=UploadStatusResponse)
async def get_upload_status(
    upload_id: UUID,
    org_id: UUID = Depends(get_org_id),
    db: AsyncSession = Depends(get_db),
):
    upload = await UploadService.get_upload_status(db, upload_id)
    if not upload or upload.org_id != org_id:
        raise HTTPException(status_code=404, detail="上传不存在")

    return UploadStatusResponse(
        upload_id=upload.id,
        status=upload.status,
        total_chunks=upload.total_chunks,
        uploaded_chunks=upload.uploaded_chunks,
        file_name=upload.file_name,
    )
