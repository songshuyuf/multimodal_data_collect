"""
Pydantic 请求/响应 Schema
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════
#  通用
# ═══════════════════════════════════════════════════

class Msg(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"


# ═══════════════════════════════════════════════════
#  认证
# ═══════════════════════════════════════════════════

class UserInfo(BaseModel):
    id: UUID
    username: str
    role: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Optional[UserInfo] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class ApiKeyCreate(BaseModel):
    label: Optional[str] = None


class ApiKeyResponse(BaseModel):
    id: UUID
    label: Optional[str]
    key: str  # 明文，只在创建时返回一次
    created_at: datetime


# ═══════════════════════════════════════════════════
#  机构
# ═══════════════════════════════════════════════════

class OrgCreate(BaseModel):
    name: str = Field(..., max_length=200)
    contact_email: Optional[str] = None


class OrgResponse(BaseModel):
    id: UUID
    name: str
    contact_email: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════
#  患者
# ═══════════════════════════════════════════════════

class PatientCreate(BaseModel):
    name: str = Field(..., max_length=100)
    age: Optional[int] = None
    gender: Optional[str] = None
    diagnosis: Optional[str] = None
    notes: Optional[str] = None


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    diagnosis: Optional[str] = None
    notes: Optional[str] = None


class PatientResponse(BaseModel):
    id: UUID
    name: str
    age: Optional[int]
    gender: Optional[str]
    diagnosis: Optional[str]
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════
#  会话
# ═══════════════════════════════════════════════════

class SessionCreate(BaseModel):
    patient_id: UUID
    session_name: str = Field(..., max_length=200)
    session_date: Optional[datetime] = None
    duration_sec: Optional[int] = 0
    notes: Optional[str] = None


class SessionResponse(BaseModel):
    id: UUID
    patient_id: UUID
    session_name: str
    session_date: Optional[datetime]
    duration_sec: int
    notes: Optional[str]
    created_at: datetime
    file_count: int = 0

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════
#  数据文件
# ═══════════════════════════════════════════════════

class DataFileResponse(BaseModel):
    id: UUID
    session_id: UUID
    modality: str
    file_name: str
    file_size: int
    file_hash: Optional[str]
    compressed: bool
    uploaded_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════
#  上传
# ═══════════════════════════════════════════════════

class UploadInitRequest(BaseModel):
    session_name: str = Field(..., max_length=200)
    file_name: str = Field(..., max_length=300)
    modality: str = Field(..., max_length=30)
    file_size: int = Field(..., ge=0)
    file_hash: Optional[str] = None
    total_chunks: int = Field(..., ge=1)
    compressed: bool = False


class UploadInitResponse(BaseModel):
    upload_id: UUID
    uploaded_chunks: int = 0  # 已上传的分块数（用于断点续传）


class UploadStatusResponse(BaseModel):
    upload_id: UUID
    status: str
    total_chunks: int
    uploaded_chunks: int
    file_name: str


class UploadCompleteResponse(BaseModel):
    status: str = "completed"
    data_file_id: UUID
    minio_key: str


# ═══════════════════════════════════════════════════
#  客户端更新
# ═══════════════════════════════════════════════════

class UpdateCheckResponse(BaseModel):
    update_available: bool
    latest_version: str = ""
    download_url: str = ""
    release_notes: str = ""
    file_size: int = 0
    file_hash: str = ""
    mandatory: bool = False


class ReleaseCreateRequest(BaseModel):
    version: str = Field(..., max_length=30)
    platform: str = Field(default="windows", max_length=20)
    release_notes: str = ""
    mandatory: bool = False


class ReleaseResponse(BaseModel):
    id: UUID
    version: str
    platform: str
    file_name: str
    file_size: int
    release_notes: str
    mandatory: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
