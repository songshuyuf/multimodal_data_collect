"""
AI 艺术诊疗数据平台 — FastAPI 入口
===================================
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.api import health, auth, uploads, patients, sessions, update, web_data

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时自动建表（生产环境应使用 alembic migrate）。"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表已就绪")
    except Exception as e:
        logger.warning("建表跳过（可能已由其他 worker 创建）: %s", e)

    import os
    os.makedirs(settings.UPLOAD_CHUNK_DIR, exist_ok=True)
    logger.info("分块暂存目录: %s", settings.UPLOAD_CHUNK_DIR)

    yield

    await engine.dispose()
    logger.info("数据库连接池已关闭")


app = FastAPI(
    title="AI 艺术诊疗数据平台",
    version="1.0.0",
    description="多模态生理信号数据管理 API",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由注册 ──
app.include_router(health.router,    prefix="/api/v1")
app.include_router(auth.router,      prefix="/api/v1")
app.include_router(uploads.router,   prefix="/api/v1")
app.include_router(patients.router,  prefix="/api/v1")
app.include_router(sessions.router,  prefix="/api/v1")
app.include_router(update.router,    prefix="/api/v1")
app.include_router(web_data.router,  prefix="/api/v1")
