"""共享范围：出入参与快照结构（对应 docs/03 §2.3 / §5.4 / §6.1）。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

ScopeMode = Literal["RANGE", "PUBLIC"]
ScopeDim = Literal["org", "role", "position", "user"]


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ScopeItem(CamelModel):
    id: str
    name: str


class ScopeUserItem(ScopeItem):
    dept_name: str | None = None


class ScopeUserWithSources(ScopeUserItem):
    sources: list[ScopeDim] = Field(default_factory=list)


class Scope(CamelModel):
    """范围快照：全链路四处场景统一结构（需求 4.0）。"""

    scope_mode: ScopeMode = "RANGE"
    orgs: list[ScopeItem] = Field(default_factory=list)
    roles: list[ScopeItem] = Field(default_factory=list)
    positions: list[ScopeItem] = Field(default_factory=list)
    users: list[ScopeUserItem] = Field(default_factory=list)
    grant_total: int = 0
    summary: str = ""


class ScopePayload(CamelModel):
    """提交给后端的范围请求体：只传 ID，不含名称与统计。"""

    scope_mode: ScopeMode = "RANGE"
    orgs: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    positions: list[str] = Field(default_factory=list)
    users: list[str] = Field(default_factory=list)

    @field_validator("orgs", "roles", "positions", "users")
    @classmethod
    def _dedupe(cls, value: list[str]) -> list[str]:
        seen: list[str] = []
        for item in value:
            key = item.strip()
            if key and key not in seen:
                seen.append(key)
        return seen

    def is_empty(self) -> bool:
        return not (self.orgs or self.roles or self.positions or self.users)

    def counts(self) -> dict[str, int]:
        return {
            "org": len(self.orgs),
            "role": len(self.roles),
            "position": len(self.positions),
            "user": len(self.users),
        }


class ScopeLimits(CamelModel):
    org: int = 50
    role: int = 50
    position: int = 50
    user: int = 200


class ScopeExpandResult(CamelModel):
    scope_mode: ScopeMode
    grant_total: int
    users: list[ScopeUserWithSources] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    limits: ScopeLimits = Field(default_factory=ScopeLimits)


class OrgNodeOut(CamelModel):
    id: str
    name: str
    level: int
    children: list["OrgNodeOut"] = Field(default_factory=list)


class OrgTreeResponse(CamelModel):
    tree: list[OrgNodeOut]


class RoleOut(CamelModel):
    id: str
    name: str
    desc: str = ""


class RoleListResponse(CamelModel):
    list: list[RoleOut]


class UserOut(CamelModel):
    id: str
    name: str
    dept_name: str
    job_no: str
    # 供前端「按组织/岗位/角色展开人员」在本地即时预览，避免每选一项就请求一次
    org_id: str = ""
    position_id: str = ""
    roles: list[str] = Field(default_factory=list)


class UserListResponse(CamelModel):
    list: list[UserOut]
    total: int
    page: int
    page_size: int


# ============================ 共享提交 ============================


class ShareSubmitPayload(CamelModel):
    assistant_ids: list[int] = Field(min_length=1, max_length=20)
    scope: ScopePayload
    change_note: str | None = Field(default=None, max_length=200)

    @field_validator("assistant_ids")
    @classmethod
    def _dedupe_ids(cls, value: list[int]) -> list[int]:
        seen: list[int] = []
        for item in value:
            if item not in seen:
                seen.append(item)
        return seen


class ShareSubmitResult(CamelModel):
    batch_no: str
    approval_ids: list[int]
    submitted_count: int
    assistant_status: str = "pending"


class ShareScopeResponse(CamelModel):
    assistant_id: int
    editable: bool
    editable_by: Literal["direct", "approval", "none"]
    scope: Scope | None = None
    pending_approval_id: int | None = None


class ShareScopeUpdatePayload(CamelModel):
    scope: ScopePayload
    change_note: str | None = Field(default=None, max_length=200)


class ShareScopeUpdateResult(CamelModel):
    assistant_id: int
    applied: bool
    approval_id: int | None = None
    scope: Scope | None = None
