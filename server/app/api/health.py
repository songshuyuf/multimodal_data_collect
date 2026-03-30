"""健康检查端点"""

from fastapi import APIRouter
from app.schemas.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()
