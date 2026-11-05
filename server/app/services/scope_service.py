"""共享范围服务：四维展开、上限校验、快照读写（对应 docs/03 §5.4 / §6.2）。

核心规则：
- 组织维度包含全部下级节点；角色/岗位按属性匹配；直接添加的人员始终纳入。
- 同一人员被多维度覆盖时只出现一次，sources 标注全部来源。
- PUBLIC 模式忽略四维，grantTotal 取公司在职人数。
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ErrorCode
from app.models.assistant import Assistant
from app.models.scope import AssistantGrant, ShareScope, ShareScopeItem
from app.schemas.scope import (
    Scope,
    ScopeExpandResult,
    ScopeItem,
    ScopeLimits,
    ScopePayload,
    ScopeUserItem,
    ScopeUserWithSources,
)
from app.services import master_data


@dataclass
class ExpandedScope:
    """展开后的范围：人员清单 + 四维快照明细。"""

    scope_mode: str
    grant_total: int
    users: list[master_data.Employee]
    user_sources: dict[str, list[str]]

    def to_scope(self, payload: ScopePayload) -> Scope:
        if self.scope_mode == "PUBLIC":
            return Scope(
                scope_mode="PUBLIC",
                orgs=[],
                roles=[],
                positions=[],
                users=[],
                grant_total=self.grant_total,
                summary="公开 · 全公司可用",
            )

        orgs = [ScopeItem(id=i, name=master_data.org_name(i)) for i in payload.orgs]
        roles = [ScopeItem(id=i, name=master_data.role_name(i)) for i in payload.roles]
        positions = [
            ScopeItem(id=i, name=master_data.position_name(i)) for i in payload.positions
        ]
        users = [
            ScopeUserItem(id=e.id, name=e.name, dept_name=e.dept_name) for e in self.users
        ]
        summary_items = [item.name for item in (*orgs, *positions, *roles)][:2]
        if not summary_items:
            summary_items = [item.name for item in users][:2]
        summary = (
            f"{'、'.join(summary_items)} 等 {self.grant_total} 人"
            if summary_items
            else ""
        )
        return Scope(
            scope_mode="RANGE",
            orgs=orgs,
            roles=roles,
            positions=positions,
            users=users,
            grant_total=self.grant_total,
            summary=summary,
        )

    def to_expand_result(self, payload: ScopePayload) -> ScopeExpandResult:
        return ScopeExpandResult(
            scope_mode=self.scope_mode,
            grant_total=self.grant_total,
            users=[
                ScopeUserWithSources(
                    id=e.id,
                    name=e.name,
                    dept_name=e.dept_name,
                    sources=self.user_sources.get(e.id, []),
                )
                for e in self.users
            ],
            counts=payload.counts(),
            limits=ScopeLimits(**master_data.SCOPE_LIMITS),
        )


class ScopeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ============================ 展开 ============================

    def expand(self, payload: ScopePayload) -> ExpandedScope:
        """四维展开为人员清单；超上限抛 SHARE_SCOPE_EXCEED_LIMIT。"""
        self.check_limits(payload)

        if payload.scope_mode == "PUBLIC":
            active = [e for e in master_data.EMPLOYEES if e.active]
            return ExpandedScope(
                scope_mode="PUBLIC",
                grant_total=master_data.headcount(),
                users=active,
                user_sources={e.id: ["user"] for e in active},
            )

        sources: dict[str, list[str]] = {}
        order: list[str] = []

        def add(employee_id: str, source: str) -> None:
            if employee_id not in sources:
                sources[employee_id] = []
                order.append(employee_id)
            if source not in sources[employee_id]:
                sources[employee_id].append(source)

        # 组织（含下级）→ 角色 → 岗位 → 直接添加
        for org_id in payload.orgs:
            for employee in master_data.search_employees(org_ids=[org_id]):
                add(employee.id, "org")
        for role_id in payload.roles:
            for employee in master_data.EMPLOYEES:
                if role_id in employee.roles:
                    add(employee.id, "role")
        for position_id in payload.positions:
            for employee in master_data.EMPLOYEES:
                if employee.position_id == position_id:
                    add(employee.id, "position")
        for user_id in payload.users:
            if master_data.employee(user_id) is not None:
                add(user_id, "user")

        users = [
            master_data.employee(employee_id)
            for employee_id in order
            if master_data.employee(employee_id) is not None
        ]
        return ExpandedScope(
            scope_mode="RANGE",
            grant_total=len(users),
            users=[u for u in users if u is not None],
            user_sources=sources,
        )

    def check_limits(self, payload: ScopePayload) -> None:
        """四维数量上限校验；RANGE 模式至少 1 项。"""
        counts = payload.counts()
        exceeded = {
            dim: count
            for dim, count in counts.items()
            if count > master_data.SCOPE_LIMITS[dim]
        }
        if exceeded:
            raise ConflictError(
                ErrorCode.SHARE_SCOPE_EXCEED_LIMIT,
                "授权范围超出上限，请减少选择",
                {"exceeded": exceeded, "limits": master_data.SCOPE_LIMITS},
            )

    # ============================ 快照读写 ============================

    def create_snapshot(
        self,
        *,
        company_id: int,
        assistant_id: int,
        stage: str,
        payload: ScopePayload,
        created_by: int,
        approval_id: int | None = None,
    ) -> ShareScope:
        """写入 share_scope + share_scope_item（不可变快照）。"""
        expanded = self.expand(payload)
        counts = payload.counts()
        scope = ShareScope(
            company_id=company_id,
            assistant_id=assistant_id,
            approval_id=approval_id,
            scope_mode=payload.scope_mode,
            stage=stage,
            org_count=counts["org"],
            role_count=counts["role"],
            position_count=counts["position"],
            user_count=counts["user"],
            grant_total=expanded.grant_total,
            created_by=created_by,
        )
        self.db.add(scope)
        self.db.flush()

        if payload.scope_mode == "RANGE":
            items: list[ShareScopeItem] = []
            items += [
                ShareScopeItem(
                    scope_id=scope.id,
                    dim="org",
                    item_id=oid,
                    item_name=master_data.org_name(oid),
                )
                for oid in payload.orgs
            ]
            items += [
                ShareScopeItem(
                    scope_id=scope.id,
                    dim="role",
                    item_id=rid,
                    item_name=master_data.role_name(rid),
                )
                for rid in payload.roles
            ]
            items += [
                ShareScopeItem(
                    scope_id=scope.id,
                    dim="position",
                    item_id=pid,
                    item_name=master_data.position_name(pid),
                )
                for pid in payload.positions
            ]
            items += [
                ShareScopeItem(
                    scope_id=scope.id,
                    dim="user",
                    item_id=uid,
                    item_name=(master_data.employee(uid).name if master_data.employee(uid) else uid),
                )
                for uid in payload.users
            ]
            for item in items:
                self.db.add(item)
        self.db.flush()
        return scope

    def load_snapshot(self, scope_id: int) -> Scope | None:
        """把落库的快照还原为前端 scope 结构。"""
        scope = self.db.scalar(select(ShareScope).where(ShareScope.id == scope_id))
        if scope is None:
            return None
        if scope.scope_mode == "PUBLIC":
            return Scope(
                scope_mode="PUBLIC",
                grant_total=scope.grant_total,
                summary="公开 · 全公司可用",
            )

        items = self.db.scalars(
            select(ShareScopeItem).where(ShareScopeItem.scope_id == scope_id)
        ).all()
        orgs = [ScopeItem(id=i.item_id, name=i.item_name) for i in items if i.dim == "org"]
        roles = [ScopeItem(id=i.item_id, name=i.item_name) for i in items if i.dim == "role"]
        positions = [
            ScopeItem(id=i.item_id, name=i.item_name) for i in items if i.dim == "position"
        ]
        direct_users = [i.item_id for i in items if i.dim == "user"]

        # 快照只存四维原始选择，人员按当前主数据重新展开（文档 Q-04：快照语义，编辑时重算）
        payload = ScopePayload(
            scope_mode="RANGE",
            orgs=[i.item_id for i in items if i.dim == "org"],
            roles=[i.item_id for i in items if i.dim == "role"],
            positions=[i.item_id for i in items if i.dim == "position"],
            users=direct_users,
        )
        expanded = self.expand(payload)
        users = [
            ScopeUserItem(id=e.id, name=e.name, dept_name=e.dept_name) for e in expanded.users
        ]
        summary_items = [item.name for item in (*orgs, *positions, *roles)][:2]
        if not summary_items:
            summary_items = [item.name for item in users][:2]
        summary = (
            f"{'、'.join(summary_items)} 等 {scope.grant_total} 人" if summary_items else ""
        )
        return Scope(
            scope_mode="RANGE",
            orgs=orgs,
            roles=roles,
            positions=positions,
            users=users,
            grant_total=scope.grant_total,
            summary=summary,
        )

    def payload_of_snapshot(self, scope_id: int) -> ScopePayload | None:
        """快照还原为四维 ID 请求体，供授权重算使用。"""
        scope = self.db.scalar(select(ShareScope).where(ShareScope.id == scope_id))
        if scope is None:
            return None
        if scope.scope_mode == "PUBLIC":
            return ScopePayload(scope_mode="PUBLIC")
        items = self.db.scalars(
            select(ShareScopeItem).where(ShareScopeItem.scope_id == scope_id)
        ).all()
        return ScopePayload(
            scope_mode="RANGE",
            orgs=[i.item_id for i in items if i.dim == "org"],
            roles=[i.item_id for i in items if i.dim == "role"],
            positions=[i.item_id for i in items if i.dim == "position"],
            users=[i.item_id for i in items if i.dim == "user"],
        )

    # ============================ 授权重算 ============================

    def rebuild_grants(
        self,
        assistant: Assistant,
        scope_id: int,
        payload: ScopePayload,
        now: datetime,
    ) -> int:
        """重算人员级授权（文档 §7.5 规则 3）：

        - 新命中人员插入，已存在但失效的恢复 valid；
        - 被本次新命中且曾移除的订阅状态重置为 subscribed；
        - 原有效但新集合未命中的置 invalid，不物理删除（保留已移除历史）；
        - 回写 assistant.authorized_count。
        """
        expanded = self.expand(payload)
        target_ids = {employee.id for employee in expanded.users}

        existing = self.db.scalars(
            select(AssistantGrant).where(AssistantGrant.assistant_id == assistant.id)
        ).all()
        existing_map = {grant.user_id: grant for grant in existing}

        for employee in expanded.users:
            grant = existing_map.get(employee.id)
            if grant is None:
                self.db.add(
                    AssistantGrant(
                        company_id=assistant.company_id,
                        assistant_id=assistant.id,
                        user_id=employee.id,
                        user_name=employee.name,
                        dept_name=employee.dept_name,
                        grant_status="valid",
                        subscribe_status="subscribed",
                        source_scope_id=scope_id,
                        grant_time=now,
                        subscribe_time=now,
                        updated_at=now,
                    )
                )
                continue

            # 曾被移除的用户被重新授权时恢复订阅（规则 3）
            if grant.grant_status != "valid" and grant.subscribe_status == "removed":
                grant.subscribe_status = "subscribed"
                grant.subscribe_time = now
            grant.grant_status = "valid"
            grant.user_name = employee.name
            grant.dept_name = employee.dept_name
            grant.source_scope_id = scope_id
            grant.updated_at = now

        for employee_id, grant in existing_map.items():
            if employee_id not in target_ids and grant.grant_status == "valid":
                grant.grant_status = "invalid"
                grant.updated_at = now

        assistant.authorized_count = len(target_ids)
        return len(target_ids)

    @staticmethod
    def diff_scope_payloads(
        before: ScopePayload | None, after: ScopePayload
    ) -> dict:
        """对比两次四维选择的差量，用于审批详情的 scopeDiff。"""

        def collect(payload: ScopePayload | None) -> dict[str, str]:
            if payload is None:
                return {}
            result: dict[str, str] = {}
            for item in payload.orgs:
                result[f"org:{item}"] = master_data.org_name(item)
            for item in payload.roles:
                result[f"role:{item}"] = master_data.role_name(item)
            for item in payload.positions:
                result[f"position:{item}"] = master_data.position_name(item)
            for item in payload.users:
                employee = master_data.employee(item)
                result[f"user:{item}"] = employee.name if employee else item
            return result

        before_map = collect(before)
        after_map = collect(after)
        added = [
            {"dim": key.split(":", 1)[0], "id": key.split(":", 1)[1], "name": name}
            for key, name in after_map.items()
            if key not in before_map
        ]
        removed = [
            {"dim": key.split(":", 1)[0], "id": key.split(":", 1)[1], "name": name}
            for key, name in before_map.items()
            if key not in after_map
        ]
        return {
            "addedCount": len(added),
            "removedCount": len(removed),
            "added": added,
            "removed": removed,
        }
