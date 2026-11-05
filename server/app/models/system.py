"""支撑表：召唤记录、审计日志、幂等键（对应 docs/02 4.13 ~ 4.15）。"""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AssistantSummon(Base):
    """召唤记录；每次召唤生成独立会话，不修改助理配置。"""

    __tablename__ = "assistant_summon"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    assistant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assistant.id", name="fk_summon_assistant"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    session_title: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class SysAuditLog(Base):
    """操作审计；按 created_at 做 RANGE COLUMNS 分区，主键为 (id, created_at)。"""

    __tablename__ = "sys_audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operator_id: Mapped[int | None] = mapped_column(BigInteger)
    operator_name: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    object_id: Mapped[str | None] = mapped_column(String(64))
    before_value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    client_ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, primary_key=True, nullable=False, server_default=func.current_timestamp()
    )


class SysIdempotency(Base):
    """幂等键记录，保留 24 小时后清理。"""

    __tablename__ = "sys_idempotency"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    biz_type: Mapped[str] = mapped_column(String(32), nullable=False)
    biz_id: Mapped[str | None] = mapped_column(String(64))
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    expired_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


__all__ = ["AssistantSummon", "SysAuditLog", "SysIdempotency"]
