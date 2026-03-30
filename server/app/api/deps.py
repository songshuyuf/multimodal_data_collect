"""
FastAPI 依赖注入 — 认证 + 数据库 Session
==========================================
客户端用 API Key 认证（Bearer token = 原始 key）。
Web 后台预留 JWT 认证。
"""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_password, decode_access_token
from app.models import ApiKey, User, Organization

bearer_scheme = HTTPBearer()


async def get_current_org(
    cred: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """
    从 Bearer token 解析出所属机构。
    优先尝试 API Key 匹配，失败后尝试 JWT（Web 后台用户）。
    """
    token = cred.credentials

    # ── 尝试 API Key ──
    result = await db.execute(select(ApiKey).where(ApiKey.is_active == True))
    for api_key in result.scalars():
        if verify_password(token, api_key.key_hash):
            from datetime import datetime, timezone
            api_key.last_used_at = datetime.now(timezone.utc)
            await db.commit()

            org = await db.get(Organization, api_key.org_id)
            if org and org.is_active:
                return org
            raise HTTPException(status_code=403, detail="机构已停用")

    # ── 尝试 JWT（Web 用户） ──
    payload = decode_access_token(token)
    if payload and "sub" in payload:
        user_id = payload["sub"]
        user = await db.get(User, UUID(user_id))
        if user and user.is_active:
            org = await db.get(Organization, user.org_id)
            if org and org.is_active:
                return org

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
    )


async def get_org_id(org: Organization = Depends(get_current_org)) -> UUID:
    """快捷依赖：直接拿 org_id。"""
    return org.id
