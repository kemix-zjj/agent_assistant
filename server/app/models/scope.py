"""共享范围快照与人员级授权模型（对应 docs/02 4.9 ~ 4.11）。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ShareScope(Base):
    """共享范围快照，stage 区分 requested / adjusted / effective。"""

    __tablename__ = "share_scope"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    assistant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assistant.id", name="fk_scope_assistant"), nullable=False
    )
    approval_id: Mapped[int | None] = mapped_column(BigInteger)
    scope_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="RANGE")
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    org_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    role_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    position_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    user_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    grant_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    items: Mapped[list["ShareScopeItem"]] = relationship(
        back_populates="scope", cascade="all, delete-orphan"
    )


class ShareScopeItem(Base):
    """范围快照的四维原始选择：org / role / position / user。"""

    __tablename__ = "share_scope_item"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scope_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("share_scope.id", name="fk_scope_item_scope", ondelete="CASCADE"),
        nullable=False,
    )
    dim: Mapped[str] = mapped_column(String(16), nullable=False)
    item_id: Mapped[str] = mapped_column(String(64), nullable=False)
    item_name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    scope: Mapped[ShareScope] = relationship(back_populates="items")


class AssistantGrant(Base):
    """授权范围展开后的人员级关系，被授权方「共享助理」列表以此表为准。"""

    __tablename__ = "assistant_grant"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    assistant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assistant.id", name="fk_grant_assistant"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_name: Mapped[str] = mapped_column(String(64), nullable=False)
    dept_name: Mapped[str | None] = mapped_column(String(128))
    grant_status: Mapped[str] = mapped_column(String(16), nullable=False, default="valid")
    subscribe_status: Mapped[str] = mapped_column(String(16), nullable=False, default="subscribed")
    source_scope_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("share_scope.id", name="fk_grant_scope")
    )
    grant_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    subscribe_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
