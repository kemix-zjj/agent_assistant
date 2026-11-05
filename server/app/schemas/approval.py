"""审批中心出入参（对应 docs/03 §7.1 ~ §7.6）。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.schemas.scope import Scope, ScopePayload


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class AssistantAvatar(CamelModel):
    type: str
    char: str
    color: str
    url: str | None = None


class ApprovalCard(CamelModel):
    """待审批列表项：列表视图与卡片视图共用同一份数据。

    `AssistantAvatar` 按 docs/03 §7.1 与前端契约保持首字母大写，
    其余字段仍走 camelCase。
    """

    approval_id: int
    approval_no: str
    approval_type: str
    approval_type_name: str
    assistant_id: int
    assistant_name: str
    assistant_avatar: AssistantAvatar = Field(alias="AssistantAvatar")
    assistant_version: str
    category_name: str
    tags: list[str] = Field(default_factory=list)
    submitter_name: str
    submitter_dept: str | None = None
    submit_time: str
    scope_summary: str = ""
    scope_mode: str = "RANGE"
    change_note: str | None = None


class ApprovalPage(CamelModel):
    list: list[ApprovalCard]
    total: int
    page: int
    page_size: int


class PendingCount(CamelModel):
    pending_count: int


class ApprovalAssistantDetail(CamelModel):
    assistant_id: int
    name: str
    avatar: AssistantAvatar
    description: str
    tags: list[str] = Field(default_factory=list)
    category_name: str
    prompt: str | None = None
    skills: list[dict] = Field(default_factory=list)
    mcps: list[dict] = Field(default_factory=list)
    knowledge_bases: list[dict] = Field(default_factory=list)
    owner_name: str | None = None
    owner_dept_name: str | None = None
    version: str


class ScopeDiffItem(CamelModel):
    dim: str
    id: str
    name: str


class ScopeDiff(CamelModel):
    added_count: int = 0
    removed_count: int = 0
    added: list[ScopeDiffItem] = Field(default_factory=list)
    removed: list[ScopeDiffItem] = Field(default_factory=list)


class ApprovalDetail(CamelModel):
    approval_id: int
    approval_no: str
    approval_type: str
    approval_type_name: str
    status: str
    assistant: ApprovalAssistantDetail
    submitter_name: str
    submitter_dept: str | None = None
    submit_time: str
    scope_adjusted: bool = False
    scope: Scope | None = None
    scope_diff: ScopeDiff | None = None
    # 提交后助理被再次编辑时提示（文档 Q-12）
    assistant_config_changed: bool = False


class ApprovalScopePayload(CamelModel):
    scope: ScopePayload


class ApprovalScopeResult(CamelModel):
    approval_id: int
    scope: Scope | None = None
    scope_diff: ScopeDiff | None = None
    scope_adjusted: bool = True


class ApprovePayload(CamelModel):
    comment: str | None = Field(default=None, max_length=200)


class RejectPayload(CamelModel):
    reject_reason: str = Field(min_length=1, max_length=200)


class ApprovalDecisionResult(CamelModel):
    approval_id: int
    status: Literal["approved", "rejected"]
    assistant_id: int
    share_status: str
    grant_total: int | None = None
    reject_reason: str | None = None
    approve_time: str
