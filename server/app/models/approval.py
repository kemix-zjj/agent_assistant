"""审批单模型（对应 docs/02 4.12）。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Approval(Base):
    """共享审批单；同一助理同一时刻仅一条 pending，由 pending_flag 生成列 + 唯一索引保证。"""

    __tablename__ = "approval"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    approval_no: Mapped[str] = mapped_column(String(32), nullable=False)
    batch_no: Mapped[str | None] = mapped_column(String(32))
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    approval_type: Mapped[str] = mapped_column(String(16), nullable=False, default="share")
    assistant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assistant.id", name="fk_approval_assistant"), nullable=False
    )
    assistant_version: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    submitter_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    submitter_name: Mapped[str] = mapped_column(String(64), nullable=False)
    submitter_dept: Mapped[str | None] = mapped_column(String(128))
    submit_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    change_note: Mapped[str | None] = mapped_column(String(200))
    requested_scope_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("share_scope.id", name="fk_approval_req_scope")
    )
    final_scope_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("share_scope.id", name="fk_approval_final_scope")
    )
    approver_id: Mapped[int | None] = mapped_column(BigInteger)
    approver_name: Mapped[str | None] = mapped_column(String(64))
    approve_time: Mapped[datetime | None] = mapped_column(DateTime)
    reject_reason: Mapped[str | None] = mapped_column(String(200))
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    assistant: Mapped["Assistant"] = relationship()  # noqa: F821 - 延迟解析避免循环导入
