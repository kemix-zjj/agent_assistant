"""资源目录、召唤、订阅、AI 生成、头像预签名出入参。

对应 docs/03 §3.7 / §3.8 / §4.3~4.5 / §8.1 / §9.1。
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ============================ 资源候选列表 ============================


class SkillOut(CamelModel):
    id: str
    name: str
    desc: str = ""
    market: str = "internal"


class McpOut(CamelModel):
    id: str
    name: str
    type: str | None = None
    market: str = "internal"


class KnowledgeBaseOut(CamelModel):
    id: str
    name: str
    document_count: int = 0
    market: str = "internal"
    files: list[str] = Field(default_factory=list)


class SkillListResponse(CamelModel):
    list: list[SkillOut]


class McpListResponse(CamelModel):
    list: list[McpOut]


class KnowledgeBaseListResponse(CamelModel):
    list: list[KnowledgeBaseOut]


# ============================ 召唤 ============================


class SummonPayload(CamelModel):
    source: str = "card"


class SummonAvatar(CamelModel):
    type: str
    char: str
    color: str
    url: str | None = None


class SummonResult(CamelModel):
    session_id: str
    session_title: str
    assistant_id: int
    assistant_name: str
    # docs/03 §3.7 与前端契约使用首字母大写的 AssistantAvatar
    assistant_avatar: SummonAvatar = Field(alias="AssistantAvatar")
    quick_questions: list[str] = Field(default_factory=list)
    created_at: str


# ============================ 订阅 ============================


class SubscriptionPayload(CamelModel):
    action: Literal["remove", "resubscribe"]


class SubscriptionResult(CamelModel):
    assistant_id: int
    subscribe_status: str
    subscribe_time: str


# ============================ AI 生成 ============================


class AiGeneratePayload(CamelModel):
    field: Literal["description", "tags", "prompt", "quickQuestions"]
    name: str = ""
    category_name: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    prompt: str | None = None
    quick_questions: list[str] = Field(default_factory=list)
    current_value: str | list[str] | None = None
    mode: Literal["auto", "generate", "polish"] = "auto"


class AiGenerateResult(CamelModel):
    field: str
    mode: str
    value: str | list[str]
    hit_limit: bool = False


# ============================ 头像预签名 ============================


class AvatarPresignPayload(CamelModel):
    file_name: str = Field(min_length=1, max_length=200)
    content_type: str = Field(min_length=1, max_length=100)
    file_size: int = Field(gt=0)


class AvatarPresignResult(CamelModel):
    upload_url: str
    object_key: str
    public_url: str
    expires_in: int
