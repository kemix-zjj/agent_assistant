"""健康检查服务。"""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import check_database
from app.schemas.health import HealthPayload


def build_health(db: Session) -> HealthPayload:
    """检查应用与数据库连通性。db 参数确保请求生命周期内会话可用。"""
    db_ok, db_error = check_database()
    return HealthPayload(
        status="ok" if db_ok else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        database="up" if db_ok else "down",
        databaseError=db_error,
    )
