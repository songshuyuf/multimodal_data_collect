"""
SQLAlchemy ORM 模型 — 多租户数据模型
====================================
Organization → ApiKey   (一对多：每个机构可有多个客户端密钥)
Organization → User     (一对多：Web 管理用户)
Organization → Patient  (一对多：按机构隔离患者数据)
Patient      → Session  (一对多：每位患者多次实验)
Session      → DataFile (一对多：每次实验多个数据文件)
Upload       → UploadChunk (一对多：分块上传跟踪)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, BigInteger, Float, Boolean, Text,
    DateTime, ForeignKey, Index, Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return uuid.uuid4()


# ═══════════════════════════════════════════════════
#  机构 / 认证
# ═══════════════════════════════════════════════════

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name = Column(String(200), unique=True, nullable=False)
    contact_email = Column(String(200))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    api_keys = relationship("ApiKey", back_populates="organization", cascade="all,delete-orphan")
    users = relationship("User", back_populates="organization", cascade="all,delete-orphan")
    patients = relationship("Patient", back_populates="organization", cascade="all,delete-orphan")


class User(Base):
    """Web 管理后台用户（暂预留，当前版本只用 API Key 认证）"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    role = Column(String(20), default="viewer")  # admin / viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    organization = relationship("Organization", back_populates="users")


class ApiKey(Base):
    """客户端 API Key（一个机构可发放多个 Key，绑定不同采集电脑）"""
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    key_hash = Column(String(200), nullable=False, unique=True, index=True)
    label = Column(String(100))  # "实验室A 主机"
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    organization = relationship("Organization", back_populates="api_keys")


# ═══════════════════════════════════════════════════
#  业务数据
# ═══════════════════════════════════════════════════

class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        Index("ix_patient_org_name", "org_id", "name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(100), nullable=False)
    age = Column(Integer)
    gender = Column(String(10))
    diagnosis = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    organization = relationship("Organization", back_populates="patients")
    sessions = relationship("Session", back_populates="patient", cascade="all,delete-orphan")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_session_patient", "patient_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    session_name = Column(String(200))  # 客户端目录名 e.g. "张三_20260325"
    session_date = Column(DateTime(timezone=True))
    duration_sec = Column(Integer, default=0)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    patient = relationship("Patient", back_populates="sessions")
    data_files = relationship("DataFile", back_populates="session", cascade="all,delete-orphan")


class DataFile(Base):
    """单个数据文件的元信息，实际内容存在 MinIO 中。"""
    __tablename__ = "data_files"
    __table_args__ = (
        Index("ix_datafile_session", "session_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    modality = Column(String(30), nullable=False)   # heeg / shimmer / shimmer_emg / video / audio / markers
    file_name = Column(String(300), nullable=False)
    file_size = Column(BigInteger, default=0)
    file_hash = Column(String(64))                   # MD5
    minio_key = Column(String(500))                  # MinIO 对象路径
    compressed = Column(Boolean, default=False)
    uploaded_at = Column(DateTime(timezone=True), default=_utcnow)

    session = relationship("Session", back_populates="data_files")


# ═══════════════════════════════════════════════════
#  分块上传跟踪
# ═══════════════════════════════════════════════════

class Upload(Base):
    """一次分块上传的整体状态跟踪。"""
    __tablename__ = "uploads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    session_name = Column(String(200))
    file_name = Column(String(300), nullable=False)
    modality = Column(String(30))
    file_size = Column(BigInteger, default=0)
    file_hash = Column(String(64))
    total_chunks = Column(Integer, default=0)
    uploaded_chunks = Column(Integer, default=0)
    compressed = Column(Boolean, default=False)
    status = Column(String(20), default="uploading")  # uploading / completed / failed
    minio_key = Column(String(500))
    data_file_id = Column(UUID(as_uuid=True), ForeignKey("data_files.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    completed_at = Column(DateTime(timezone=True))

    chunks = relationship("UploadChunk", back_populates="upload", cascade="all,delete-orphan")


class UploadChunk(Base):
    """单个分块的接收记录。"""
    __tablename__ = "upload_chunks"
    __table_args__ = (
        Index("ix_chunk_upload_idx", "upload_id", "chunk_index", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    upload_id = Column(UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_size = Column(Integer, default=0)
    received_at = Column(DateTime(timezone=True), default=_utcnow)

    upload = relationship("Upload", back_populates="chunks")


# ═══════════════════════════════════════════════════
#  客户端版本发布
# ═══════════════════════════════════════════════════

class AppRelease(Base):
    """客户端安装包版本记录，用于自动更新。"""
    __tablename__ = "app_releases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    version = Column(String(30), nullable=False, unique=True, index=True)
    platform = Column(String(20), default="windows")  # windows / macos / linux
    file_name = Column(String(300), nullable=False)
    file_size = Column(BigInteger, default=0)
    file_hash = Column(String(64))
    minio_key = Column(String(500))
    release_notes = Column(Text, default="")
    mandatory = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
