"""助理接口出入参（对应 docs/03 §3.1 ~ §3.6）。

出入参均使用 camelCase 与前端契约一致；Python 侧为 snake_case 属性。
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator
from pydantic.alias_generators import to_camel

AssistantAction = Literal[
    "summon", "edit", "delete", "shareScope", "remove", "resubscribe", "share", "resubmit"
]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ============================ 入参 ============================


class AssistantUpsertPayload(BaseModel):
    """创建与编辑共用；编辑为全量覆盖。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str = Field(min_length=2, max_length=20)
    avatar_type: Literal["char", "image"] = "char"
    avatar_char: str | None = Field(default=None, max_length=2)
    avatar_url: str | None = Field(default=None, max_length=512)
    avatar_color: str = Field(default="#3685F2", pattern=r"^#[0-9A-Fa-f]{6}$")
    description: str = Field(min_length=10, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=5)
    category_id: int
    prompt: str = Field(min_length=1, max_length=4000)
    skill_ids: list[str] = Field(default_factory=list, max_length=20)
    mcp_ids: list[str] = Field(default_factory=list, max_length=20)
    knowledge_base_ids: list[str] = Field(default_factory=list, max_length=10)
    quick_questions: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("name", "description")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("avatar_char")
    @classmethod
    def _blank_avatar_char(cls, value: str | None) -> str | None:
        return value if value and value.strip() else None

    @field_validator("tags")
    @classmethod
    def _check_tags(cls, value: list[str]) -> list[str]:
        result: list[str] = []
        for tag in value:
            name = tag.strip()
            if not name:
                raise ValueError("标签不能为空")
            if len(name) > 8:
                raise ValueError("单个标签不超过 8 个字符")
            if name in result:
                raise ValueError("标签不能重复")
            result.append(name)
        return result

    @field_validator("quick_questions")
    @classmethod
    def _check_quick_questions(cls, value: list[str]) -> list[str]:
        result: list[str] = []
        for question in value:
            content = question.strip()
            if not content:
                raise ValueError("快速问题不能为空")
            if len(content) > 200:
                raise ValueError("单条快速问题不超过 200 个字符")
            if content in result:
                raise ValueError("快速问题不能重复")
            result.append(content)
        return result

    @field_validator("skill_ids", "mcp_ids", "knowledge_base_ids")
    @classmethod
    def _dedupe_ids(cls, value: list[str]) -> list[str]:
        seen: list[str] = []
        for item in value:
            if item not in seen:
                seen.append(item)
        return seen


# ============================ 出参 ============================


class ResourceRef(CamelModel):
    id: str
    name: str


class McpRef(ResourceRef):
    type: str | None = None


class KnowledgeBaseRef(ResourceRef):
    document_count: int | None = None


class SharedFrom(CamelModel):
    owner_name: str
    owner_dept_name: str | None = None


class AssistantCard(CamelModel):
    """列表卡片：不含提示词与能力组成明细。"""

    assistant_id: int
    name: str
    avatar_type: str
    avatar_char: str | None
    avatar_url: str | None
    avatar_color: str
    category_id: int
    category_name: str
    tags: list[str]
    description: str
    source: str
    share_status: str | None = None
    subscribe_status: str | None = None
    version: str
    owner_name: str | None = None
    owner_title: str | None = None
    shared_from: SharedFrom | None = None
    reject_reason: str | None = None
    last_approver_name: str | None = None
    last_approve_time: str | None = None
    authorized_count: int = 0
    created_at: str
    updated_at: str
    authorized_at: str | None = None
    actions: list[AssistantAction] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def description_truncated(self) -> str:
        return f"{self.description[:60]}…" if len(self.description) > 60 else self.description


class VersionHistoryItem(CamelModel):
    version: str
    action: str
    action_name: str
    operator_name: str
    remark: str
    created_at: str


class AssistantDetail(CamelModel):
    assistant_id: int
    name: str
    avatar_type: str
    avatar_char: str | None
    avatar_url: str | None
    avatar_color: str
    description: str
    tags: list[str]
    category_id: int
    category_name: str
    source: str
    share_status: str | None = None
    version: str
    owner_name: str | None = None
    owner_dept_name: str | None = None
    created_at: str
    updated_at: str
    # 被授权方视角下置为 null（需求 5.2）
    prompt: str | None = None
    skills: list[ResourceRef] | None = None
    mcps: list[McpRef] | None = None
    knowledge_bases: list[KnowledgeBaseRef] | None = None
    quick_questions: list[str] = Field(default_factory=list)
    share_scope: dict | None = None
    version_history: list[VersionHistoryItem] = Field(default_factory=list)


class DeleteImpact(CamelModel):
    assistant_id: int
    name: str
    authorized_count: int
    pending_apply_count: int


class DeleteResult(CamelModel):
    assistant_id: int
    deleted: bool


class AssistantPage(CamelModel):
    list: list[AssistantCard]
    total: int
    page: int
    page_size: int
