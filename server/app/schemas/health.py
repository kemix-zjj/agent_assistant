"""健康检查出入参。"""

from pydantic import BaseModel


class HealthPayload(BaseModel):
    status: str
    app: str
    version: str
    database: str
    databaseError: str | None = None
