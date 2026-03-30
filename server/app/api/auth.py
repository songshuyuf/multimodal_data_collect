"""
认证路由 — API Key 管理 + JWT 登录
===================================
管理员通过 JWT 登录后可为机构签发/吊销 API Key。
客户端持 API Key 上传数据，无需交互式登录。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, create_access_token, generate_api_key,
)
from app.models import User, ApiKey, Organization
from app.schemas.schemas import (
    LoginRequest, TokenResponse, ApiKeyCreate, ApiKeyResponse, Msg,
    OrgCreate, OrgResponse,
)
from app.api.deps import get_current_org

router = APIRouter(prefix="/auth", tags=["auth"])


# ── JWT 登录（Web 管理后台用） ──

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.username == body.username)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已停用")

    token = create_access_token(data={"sub": str(user.id), "org": str(user.org_id)})
    from app.schemas.schemas import UserInfo
    return TokenResponse(
        access_token=token,
        user=UserInfo(id=user.id, username=user.username, role=user.role),
    )


# ── API Key 管理 ──

@router.post("/api-keys", response_model=ApiKeyResponse)
async def create_api_key(
    body: ApiKeyCreate,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    raw_key = generate_api_key()
    api_key = ApiKey(
        org_id=org.id,
        key_hash=hash_password(raw_key),
        label=body.label,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return ApiKeyResponse(
        id=api_key.id,
        label=api_key.label,
        key=raw_key,
        created_at=api_key.created_at,
    )


@router.delete("/api-keys/{key_id}", response_model=Msg)
async def revoke_api_key(
    key_id: str,
    org: Organization = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    from uuid import UUID
    api_key = await db.get(ApiKey, UUID(key_id))
    if not api_key or api_key.org_id != org.id:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    api_key.is_active = False
    await db.commit()
    return Msg(detail="已吊销")


# ── 初始化：创建机构 + 首个管理员（首次部署时用） ──

@router.post("/setup", response_model=OrgResponse)
async def initial_setup(
    body: OrgCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    首次部署初始化：创建机构 + admin 用户 + 首个 API Key。
    仅在数据库无任何机构时可用。
    """
    existing = await db.execute(select(Organization))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="系统已初始化，请通过管理员登录操作")

    org = Organization(name=body.name, contact_email=body.contact_email)
    db.add(org)
    await db.flush()

    admin = User(
        org_id=org.id,
        username="admin",
        hashed_password=hash_password("admin123"),
        role="admin",
    )
    db.add(admin)

    raw_key = generate_api_key()
    api_key = ApiKey(
        org_id=org.id,
        key_hash=hash_password(raw_key),
        label="默认客户端密钥",
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(org)

    print(f"\n{'='*50}")
    print(f"  初始化完成!")
    print(f"  机构: {org.name}")
    print(f"  管理员: admin / admin123  (请尽快修改密码)")
    print(f"  API Key: {raw_key}")
    print(f"  (此 Key 仅显示一次，请妥善保存)")
    print(f"{'='*50}\n")

    return OrgResponse.model_validate(org)
