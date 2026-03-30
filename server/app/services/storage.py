"""
MinIO 对象存储服务
==================
封装 MinIO SDK，提供文件上传/下载/删除。
"""

import io
import logging
from typing import Optional

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """MinIO 对象存储封装"""

    def __init__(self):
        self._client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self._bucket = settings.MINIO_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
                logger.info("创建 MinIO bucket: %s", self._bucket)
        except S3Error as e:
            logger.error("MinIO bucket 初始化失败: %s", e)

    def put_object(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> bool:
        try:
            self._client.put_object(
                self._bucket, key,
                io.BytesIO(data), len(data),
                content_type=content_type,
            )
            return True
        except S3Error as e:
            logger.error("MinIO put_object 失败 [%s]: %s", key, e)
            return False

    def put_file(self, key: str, file_path: str, content_type: str = "application/octet-stream") -> bool:
        try:
            self._client.fput_object(
                self._bucket, key, file_path,
                content_type=content_type,
            )
            return True
        except S3Error as e:
            logger.error("MinIO fput_object 失败 [%s]: %s", key, e)
            return False

    def get_object(self, key: str) -> Optional[bytes]:
        try:
            resp = self._client.get_object(self._bucket, key)
            data = resp.read()
            resp.close()
            resp.release_conn()
            return data
        except S3Error as e:
            logger.error("MinIO get_object 失败 [%s]: %s", key, e)
            return None

    def delete_object(self, key: str) -> bool:
        try:
            self._client.remove_object(self._bucket, key)
            return True
        except S3Error as e:
            logger.error("MinIO delete_object 失败 [%s]: %s", key, e)
            return False

    def stat_object(self, key: str):
        try:
            return self._client.stat_object(self._bucket, key)
        except S3Error:
            return None

    def presigned_get_url(self, key: str, expires_hours: int = 1) -> Optional[str]:
        """生成临时下载链接（预留，供后续 Web 前端下载数据用）。"""
        from datetime import timedelta
        try:
            return self._client.presigned_get_object(
                self._bucket, key, expires=timedelta(hours=expires_hours)
            )
        except S3Error as e:
            logger.error("presigned_get_url 失败 [%s]: %s", key, e)
            return None


storage_service = StorageService()
