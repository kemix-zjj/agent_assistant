"""助理主表与能力组成关联模型（对应 docs/02 4.1 ~ 4.8）。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AssistantCategory(Base):
    """助理分类字典。唯一性由生成列 active_flag + uk_category_company_name 保证。"""

    __tablename__ = "assistant_category"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(10), nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_builtin: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class Assistant(Base):
    """助理主表。"""

    __tablename__ = "assistant"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    avatar_type: Mapped[str] = mapped_column(String(10), nullable=False, default="char")
    avatar_char: Mapped[str | None] = mapped_column(String(2))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    avatar_color: Mapped[str] = mapped_column(String(16), nullable=False, default="#3685F2")
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    category_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assistant_category.id", name="fk_assistant_category"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="custom")
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger)
    owner_name: Mapped[str | None] = mapped_column(String(64))
    owner_dept_name: Mapped[str | None] = mapped_column(String(128))
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    share_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unshared")
    # 审批子类：share 共享审批 / change 调整审批 / scope 授权审批 / offline 下架审批
    pending_type: Mapped[str | None] = mapped_column(String(16))
    # 拒绝子类：与 pending_type 同构，仅 rejected 状态有值
    reject_type: Mapped[str | None] = mapped_column(String(16))
    # 是否曾共享成功过：决定版本号生成口径与删除资格
    has_shared: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 为空串表示「未发布」：仅在审批通过时生成或递增
    version: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    authorized_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    offline_reason: Mapped[str | None] = mapped_column(String(200))
    last_reject_reason: Mapped[str | None] = mapped_column(String(200))
    last_approver_name: Mapped[str | None] = mapped_column(String(64))
    last_approve_time: Mapped[datetime | None] = mapped_column(DateTime)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)

    category: Mapped[AssistantCategory] = relationship(lazy="joined")
    skills: Mapped[list["AssistantSkillRel"]] = relationship(
        back_populates="assistant", cascade="all, delete-orphan", order_by="AssistantSkillRel.sort_no"
    )
    mcps: Mapped[list["AssistantMcpRel"]] = relationship(
        back_populates="assistant", cascade="all, delete-orphan", order_by="AssistantMcpRel.sort_no"
    )
    knowledge_bases: Mapped[list["AssistantKbRel"]] = relationship(
        back_populates="assistant", cascade="all, delete-orphan", order_by="AssistantKbRel.sort_no"
    )
    tags: Mapped[list["AssistantTag"]] = relationship(
        back_populates="assistant", cascade="all, delete-orphan", order_by="AssistantTag.sort_no"
    )
    quick_questions: Mapped[list["AssistantQuickQuestion"]] = relationship(
        back_populates="assistant",
        cascade="all, delete-orphan",
        order_by="AssistantQuickQuestion.sort_no",
    )
    version_history: Mapped[list["AssistantVersionHistory"]] = relationship(
        back_populates="assistant",
        cascade="all, delete-orphan",
        # 同一次操作可能落在同一秒，追加 id 倒序保证最新记录在首位
        order_by="(AssistantVersionHistory.created_at.desc(), AssistantVersionHistory.id.desc())",
    )


class AssistantSkillRel(Base):
    __tablename__ = "assistant_skill_rel"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assistant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assistant.id", name="fk_skill_assistant", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    assistant: Mapped[Assistant] = relationship(back_populates="skills")


class AssistantMcpRel(Base):
    __tablename__ = "assistant_mcp_rel"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assistant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assistant.id", name="fk_mcp_assistant", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_name: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(32))
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    assistant: Mapped[Assistant] = relationship(back_populates="mcps")


class AssistantKbRel(Base):
    __tablename__ = "assistant_kb_rel"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assistant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assistant.id", name="fk_kb_assistant", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    assistant: Mapped[Assistant] = relationship(back_populates="knowledge_bases")


class AssistantTag(Base):
    __tablename__ = "assistant_tag"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assistant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assistant.id", name="fk_tag_assistant", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(8), nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    assistant: Mapped[Assistant] = relationship(back_populates="tags")


class AssistantQuickQuestion(Base):
    __tablename__ = "assistant_quick_question"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assistant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assistant.id", name="fk_qq_assistant", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    assistant: Mapped[Assistant] = relationship(back_populates="quick_questions")


class AssistantVersionHistory(Base):
    __tablename__ = "assistant_version_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assistant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("assistant.id", name="fk_version_assistant", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    operator_id: Mapped[int | None] = mapped_column(BigInteger)
    operator_name: Mapped[str] = mapped_column(String(64), nullable=False)
    remark: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    assistant: Mapped[Assistant] = relationship(back_populates="version_history")
