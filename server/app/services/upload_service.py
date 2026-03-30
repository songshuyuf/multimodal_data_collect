"""
分块上传服务
============
处理客户端分块上传：初始化 → 接收分块(磁盘暂存) → 合并 → 存入 MinIO → 写入 DataFile。
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Upload, UploadChunk, DataFile, Session, Patient
from app.services.storage import storage_service

logger = logging.getLogger(__name__)


class UploadService:

    @staticmethod
    async def init_upload(
        db: AsyncSession,
        org_id: UUID,
        session_name: str,
        file_name: str,
        modality: str,
        file_size: int,
        file_hash: Optional[str],
        total_chunks: int,
        compressed: bool,
    ) -> Tuple[UUID, int]:
        """
        初始化一次上传。如果同文件哈希的上传已存在且未完成，返回已有记录实现断点续传。
        Returns: (upload_id, already_uploaded_chunks)
        """
        # 断点续传：查找同 hash 且未完成的上传
        if file_hash:
            existing = await db.execute(
                select(Upload).where(
                    Upload.org_id == org_id,
                    Upload.file_hash == file_hash,
                    Upload.status == "uploading",
                )
            )
            upload = existing.scalar_one_or_none()
            if upload:
                logger.info("断点续传: upload=%s, 已传 %d/%d",
                            upload.id, upload.uploaded_chunks, upload.total_chunks)
                return upload.id, upload.uploaded_chunks

        upload = Upload(
            org_id=org_id,
            session_name=session_name,
            file_name=file_name,
            modality=modality,
            file_size=file_size,
            file_hash=file_hash,
            total_chunks=total_chunks,
            compressed=compressed,
            status="uploading",
        )
        db.add(upload)
        await db.commit()
        await db.refresh(upload)

        chunk_dir = os.path.join(settings.UPLOAD_CHUNK_DIR, str(upload.id))
        os.makedirs(chunk_dir, exist_ok=True)

        logger.info("新上传: upload=%s, file=%s, chunks=%d", upload.id, file_name, total_chunks)
        return upload.id, 0

    @staticmethod
    async def receive_chunk(
        db: AsyncSession,
        upload_id: UUID,
        chunk_index: int,
        data: bytes,
    ) -> bool:
        """接收并暂存一个分块。"""
        upload = await db.get(Upload, upload_id)
        if not upload or upload.status != "uploading":
            return False

        if chunk_index < 0 or chunk_index >= upload.total_chunks:
            return False

        # 幂等：已存在则跳过
        existing = await db.execute(
            select(UploadChunk).where(
                UploadChunk.upload_id == upload_id,
                UploadChunk.chunk_index == chunk_index,
            )
        )
        if existing.scalar_one_or_none():
            return True

        chunk_dir = os.path.join(settings.UPLOAD_CHUNK_DIR, str(upload_id))
        os.makedirs(chunk_dir, exist_ok=True)
        chunk_path = os.path.join(chunk_dir, f"{chunk_index:06d}")

        with open(chunk_path, "wb") as f:
            f.write(data)

        chunk_record = UploadChunk(
            upload_id=upload_id,
            chunk_index=chunk_index,
            chunk_size=len(data),
        )
        db.add(chunk_record)
        upload.uploaded_chunks = chunk_index + 1
        await db.commit()

        return True

    @staticmethod
    async def complete_upload(
        db: AsyncSession,
        upload_id: UUID,
        org_id: UUID,
    ) -> Optional[DataFile]:
        """
        合并所有分块 → 上传到 MinIO → 创建 DataFile 记录 → 清理临时文件。
        """
        upload = await db.get(Upload, upload_id)
        if not upload or upload.status != "uploading":
            return None
        if upload.org_id != org_id:
            return None

        chunk_count = await db.scalar(
            select(func.count()).select_from(UploadChunk).where(
                UploadChunk.upload_id == upload_id
            )
        )
        if chunk_count < upload.total_chunks:
            logger.warning("分块不完整: %d/%d", chunk_count, upload.total_chunks)
            return None

        chunk_dir = os.path.join(settings.UPLOAD_CHUNK_DIR, str(upload_id))
        merged_path = os.path.join(chunk_dir, "_merged")

        # ─ 合并分块 ─
        with open(merged_path, "wb") as out:
            for i in range(upload.total_chunks):
                part = os.path.join(chunk_dir, f"{i:06d}")
                with open(part, "rb") as p:
                    while True:
                        buf = p.read(8192)
                        if not buf:
                            break
                        out.write(buf)

        # ─ 确定 MinIO key ─
        # 格式: org_id/session_name/modality/file_name
        minio_key = f"{upload.org_id}/{upload.session_name}/{upload.modality}/{upload.file_name}"

        content_type = "application/gzip" if upload.compressed else "application/octet-stream"
        ok = storage_service.put_file(minio_key, merged_path, content_type)
        if not ok:
            logger.error("MinIO 上传失败: %s", minio_key)
            return None

        # ─ 查找或创建 Session ─
        session = await _ensure_session(db, org_id, upload.session_name)

        # ─ 创建 DataFile ─
        data_file = DataFile(
            session_id=session.id,
            modality=upload.modality,
            file_name=upload.file_name,
            file_size=upload.file_size,
            file_hash=upload.file_hash,
            minio_key=minio_key,
            compressed=upload.compressed,
        )
        db.add(data_file)

        upload.status = "completed"
        upload.minio_key = minio_key
        upload.data_file_id = data_file.id
        upload.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(data_file)

        # ─ 清理临时文件 ─
        import shutil
        try:
            shutil.rmtree(chunk_dir)
        except OSError as e:
            logger.warning("清理临时目录失败: %s", e)

        logger.info("上传完成: %s → %s", upload.file_name, minio_key)
        return data_file

    @staticmethod
    async def get_upload_status(db: AsyncSession, upload_id: UUID) -> Optional[Upload]:
        return await db.get(Upload, upload_id)


async def _ensure_session(db: AsyncSession, org_id: UUID, session_name: str) -> Session:
    """
    根据 session_name 查找已有 Session，不存在则自动创建。
    session_name 格式通常为 "患者名_日期"，暂挂到 org 下匿名患者。
    """
    result = await db.execute(
        select(Session).join(Patient).where(
            Patient.org_id == org_id,
            Session.session_name == session_name,
        )
    )
    session = result.scalar_one_or_none()
    if session:
        return session

    # 自动创建匿名患者 + 会话
    patient_name = session_name.rsplit("_", 1)[0] if "_" in session_name else session_name
    result = await db.execute(
        select(Patient).where(
            Patient.org_id == org_id,
            Patient.name == patient_name,
        )
    )
    patient = result.scalar_one_or_none()
    if not patient:
        patient = Patient(org_id=org_id, name=patient_name)
        db.add(patient)
        await db.flush()

    session = Session(
        patient_id=patient.id,
        session_name=session_name,
        session_date=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.flush()
    return session
