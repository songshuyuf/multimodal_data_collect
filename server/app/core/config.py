"""
应用配置 — 从环境变量/.env 读取，Pydantic Settings 校验
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ── 数据库 ──
    DATABASE_URL: str = "postgresql+asyncpg://art_treat:art_treat_2026@localhost:5432/art_treat"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://art_treat:art_treat_2026@localhost:5432/art_treat"

    # ── MinIO ──
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin2026"
    MINIO_BUCKET: str = "art-treat-data"
    MINIO_SECURE: bool = False

    # ── JWT ──
    SECRET_KEY: str = "CHANGE-ME-TO-A-RANDOM-STRING-AT-LEAST-32-CHARS"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h

    # ── 应用 ──
    DEBUG: bool = False
    CORS_ORIGINS: List[str] = ["*"]
    UPLOAD_CHUNK_DIR: str = "/tmp/uploads"
    SERVER_HOST: str = "172.16.55.196:8000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
