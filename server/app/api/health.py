"""健康检查路由（不带 /api/v1 前缀，供探针直接访问）。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import ok
from app.schemas.health import HealthPayload
from app.services.health_service import build_health

router = APIRouter(tags=["health"])


@router.get("/health", summary="健康检查")
def health(db: Session = Depends(get_db)) -> dict:
    payload: HealthPayload = build_health(db)
    return ok(payload.model_dump())
