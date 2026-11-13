"""助理数据访问层：列表（三范围 UNION）、详情、写入与删除。

分层约束：本层只做查询与持久化，不含权限判断与业务规则。
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    String,
    and_,
    case,
    cast,
    exists,
    func,
    literal,
    or_,
    select,
    union_all,
)
from sqlalchemy.orm import Session, selectinload

from app.models.approval import Approval
from app.models.assistant import (
    Assistant,
    AssistantKbRel,
    AssistantMcpRel,
    AssistantQuickQuestion,
    AssistantSkillRel,
    AssistantTag,
    AssistantVersionHistory,
)
from app.models.scope import AssistantGrant, ShareScope

_EAGER = (
    selectinload(Assistant.category),
    selectinload(Assistant.tags),
    selectinload(Assistant.quick_questions),
    selectinload(Assistant.skills),
    selectinload(Assistant.mcps),
    selectinload(Assistant.knowledge_bases),
    selectinload(Assistant.version_history),
)


class AssistantRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ---------------- 列表 ----------------

    def _base_scope_queries(
        self, company_id: int, user_id: int, grant_user_id: str | None
    ) -> tuple[Any, Any, Any]:
        """返回 (平台, 自建, 共享) 三段 id+rank+sort_time 查询。

        grant_user_id 为主数据人员 ID（assistant_grant.user_id 的取值）；
        登录账号与主数据人员无映射时，共享段为空。
        """
        platform = select(
            Assistant.id.label("id"),
            literal(0).label("rank"),
            Assistant.created_at.label("sort_time"),
        ).where(
            Assistant.company_id == company_id,
            Assistant.source == "platform",
            Assistant.deleted_at.is_(None),
        )

        # 我的助理：固定按 已共享 → 审批中（含下架审批中）→ 已拒绝 → 未共享 → 已下架
        status_rank = case(
            (Assistant.share_status == "approved", 0),
            (Assistant.share_status == "pending", 1),
            (Assistant.share_status == "rejected", 2),
            (Assistant.share_status == "unshared", 3),
            (Assistant.share_status == "offline", 4),
            else_=9,
        )
        mine = select(
            Assistant.id.label("id"),
            status_rank.label("rank"),
            Assistant.updated_at.label("sort_time"),
        ).where(
            Assistant.company_id == company_id,
            Assistant.source.in_(("custom", "thirdparty")),
            Assistant.owner_user_id == user_id,
            Assistant.deleted_at.is_(None),
        )

        # 共享段：别人授权给我的助理（排除自己创建、自己也被授权的情况）
        # 排序：已订阅在前、已移除在后；同状态内按授权生效时间倒序
        subscribe_rank = case(
            (AssistantGrant.subscribe_status == "subscribed", 2), else_=3
        )
        shared = (
            select(
                Assistant.id.label("id"),
                subscribe_rank.label("rank"),
                AssistantGrant.grant_time.label("sort_time"),
            )
            .join(AssistantGrant, AssistantGrant.assistant_id == Assistant.id)
            .where(
                Assistant.company_id == company_id,
                AssistantGrant.company_id == company_id,
                AssistantGrant.user_id == (grant_user_id or ""),
                AssistantGrant.grant_status == "valid",
                Assistant.owner_user_id != user_id,
                Assistant.deleted_at.is_(None),
            )
        )

        return platform, mine, shared

    def _apply_filters(self, stmt: Any, category_id: int | None, keyword: str | None) -> Any:
        if category_id is not None:
            stmt = stmt.where(Assistant.category_id == category_id)
        if keyword:
            like = f"%{keyword}%"
            tag_hit = exists().where(
                and_(AssistantTag.assistant_id == Assistant.id, AssistantTag.name.like(like))
            )
            stmt = stmt.where(or_(Assistant.name.like(like), tag_hit))
        return stmt

    def _all_scope_mine_query(self, company_id: int, user_id: int) -> Any:
        """全部页签中的自建段：仅计入「本质已共享」的助理。

        审批中 / 已拒绝只有「共享审批」子类属于未共享，其余三类均曾共享成功；
        因此审批中仅收纳调整 / 授权 / 下架三类，已拒绝排除「已拒绝 · 共享审批」。
        """
        return select(
            Assistant.id.label("id"),
            literal(1).label("rank"),
            Assistant.updated_at.label("sort_time"),
        ).where(
            Assistant.company_id == company_id,
            Assistant.source.in_(("custom", "thirdparty")),
            Assistant.owner_user_id == user_id,
            Assistant.deleted_at.is_(None),
            or_(
                Assistant.share_status == "approved",
                and_(
                    Assistant.share_status == "pending",
                    Assistant.pending_type.in_(("change", "scope", "offline")),
                ),
                and_(
                    Assistant.share_status == "rejected",
                    or_(Assistant.reject_type.is_(None), Assistant.reject_type != "share"),
                ),
            ),
        )

    def list_ids(
        self,
        *,
        company_id: int,
        user_id: int,
        grant_user_id: str | None,
        scope: str,
        category_id: int | None,
        keyword: str | None,
        status_filter: str | None,
        subscribe_filter: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[int], int]:
        """返回当前页助理 ID 与总数；顺序遵循需求 4.0「页签构成与排序统一」。"""
        platform, mine, shared = self._base_scope_queries(company_id, user_id, grant_user_id)

        if scope == "mine":
            part = self._apply_filters(mine, category_id, keyword)
            if status_filter == "pending":
                # 「审批中」聚合共享 / 调整 / 授权 / 下架四类审批中
                part = part.where(Assistant.share_status == "pending")
            elif status_filter:
                part = part.where(Assistant.share_status == status_filter)
            base = part
        elif scope == "shared":
            part = self._apply_filters(shared, category_id, keyword)
            if subscribe_filter:
                part = part.where(AssistantGrant.subscribe_status == subscribe_filter)
            base = part
        else:
            # 全部页签 = 平台内置 + 已共享 + 已订阅三种状态：
            # 「已共享」含调整 / 授权 / 下架审批中与对应已拒绝（不含「共享审批」两类）
            shared = shared.where(AssistantGrant.subscribe_status == "subscribed")
            base = union_all(
                self._apply_filters(platform, category_id, keyword),
                self._apply_filters(
                    self._all_scope_mine_query(company_id, user_id), category_id, keyword
                ),
                self._apply_filters(shared, category_id, keyword),
            )

        base = base.subquery()
        total = self.db.scalar(select(func.count()).select_from(base)) or 0

        rows = self.db.execute(
            select(base.c.id)
            .order_by(base.c.rank.asc(), base.c.sort_time.desc(), base.c.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()

        return [row.id for row in rows], int(total)

    def load_many(self, ids: list[int]) -> list[Assistant]:
        if not ids:
            return []
        rows = self.db.scalars(
            select(Assistant).options(*_EAGER).where(Assistant.id.in_(ids))
        ).all()
        order = {assistant_id: index for index, assistant_id in enumerate(ids)}
        return sorted(rows, key=lambda row: order.get(row.id, 0))

    def find_grants(
        self, grant_user_id: str | None, assistant_ids: list[int]
    ) -> dict[int, AssistantGrant]:
        if not grant_user_id or not assistant_ids:
            return {}
        rows = self.db.scalars(
            select(AssistantGrant).where(
                AssistantGrant.user_id == grant_user_id,
                AssistantGrant.assistant_id.in_(assistant_ids),
            )
        ).all()
        return {row.assistant_id: row for row in rows}

    def find_effective_scope_ids(self, assistant_ids: list[int]) -> dict[int, int]:
        """批量取每个助理最新的 effective 范围快照 ID。"""
        if not assistant_ids:
            return {}
        rows = self.db.execute(
            select(ShareScope.assistant_id, func.max(ShareScope.id))
            .where(
                ShareScope.assistant_id.in_(assistant_ids),
                ShareScope.stage == "effective",
            )
            .group_by(ShareScope.assistant_id)
        ).all()
        return {assistant_id: int(scope_id) for assistant_id, scope_id in rows}

    # ---------------- 详情 ----------------

    def find_by_id(self, assistant_id: int, company_id: int) -> Assistant | None:
        return self.db.scalar(
            select(Assistant)
            .options(*_EAGER)
            # expire_on_commit=False 时同一会话内会复用缓存集合，写入后需强制刷新
            .execution_options(populate_existing=True)
            .where(
                Assistant.id == assistant_id,
                Assistant.company_id == company_id,
                Assistant.deleted_at.is_(None),
            )
        )

    def find_grant(
        self, assistant_id: int, grant_user_id: str | None
    ) -> AssistantGrant | None:
        if not grant_user_id:
            return None
        return self.db.scalar(
            select(AssistantGrant).where(
                AssistantGrant.assistant_id == assistant_id,
                AssistantGrant.user_id == grant_user_id,
            )
        )

    def find_name_conflict(
        self, company_id: int, name: str, exclude_id: int | None = None
    ) -> Assistant | None:
        stmt = select(Assistant.id).where(
            Assistant.company_id == company_id,
            Assistant.name == name,
            Assistant.deleted_at.is_(None),
        )
        if exclude_id is not None:
            stmt = stmt.where(Assistant.id != exclude_id)
        return self.db.scalar(stmt)

    # ---------------- 写入 ----------------

    def create(self, **fields: Any) -> Assistant:
        row = Assistant(**fields)
        self.db.add(row)
        self.db.flush()
        return row

    def replace_relations(
        self,
        assistant: Assistant,
        *,
        tags: list[str],
        quick_questions: list[str],
        skills: list[tuple[str, str]],
        mcps: list[tuple[str, str, str | None]],
        knowledge_bases: list[tuple[str, str]],
    ) -> None:
        """全量覆盖能力组成：先清空再按保存顺序写入。

        通过 ORM 集合操作而非直接 db.delete，保证会话内集合状态同步，
        避免 expire_on_commit=False 下读到陈旧数据。
        """
        assistant.tags.clear()
        assistant.quick_questions.clear()
        assistant.skills.clear()
        assistant.mcps.clear()
        assistant.knowledge_bases.clear()
        self.db.flush()

        assistant.tags.extend(
            AssistantTag(name=name, sort_no=index) for index, name in enumerate(tags)
        )
        assistant.quick_questions.extend(
            AssistantQuickQuestion(content=content, sort_no=index)
            for index, content in enumerate(quick_questions)
        )
        assistant.skills.extend(
            AssistantSkillRel(resource_id=rid, resource_name=name, sort_no=index)
            for index, (rid, name) in enumerate(skills)
        )
        assistant.mcps.extend(
            AssistantMcpRel(
                resource_id=rid, resource_name=name, resource_type=rtype, sort_no=index
            )
            for index, (rid, name, rtype) in enumerate(mcps)
        )
        assistant.knowledge_bases.extend(
            AssistantKbRel(resource_id=rid, resource_name=name, sort_no=index)
            for index, (rid, name) in enumerate(knowledge_bases)
        )

    def add_version_history(
        self,
        assistant: Assistant,
        *,
        version: str,
        action: str,
        operator_id: int | None,
        operator_name: str,
        remark: str | None = None,
        created_at: datetime | None = None,
    ) -> None:
        """通过关系追加，flush 后 id 可用，保证同一秒内的记录也能正确排序。"""
        assistant.version_history.append(
            AssistantVersionHistory(
                version=version,
                action=action,
                operator_id=operator_id,
                operator_name=operator_name,
                remark=remark,
                created_at=created_at or datetime.now(),
            )
        )
        self.db.flush()

    # ---------------- 删除 ----------------

    def count_valid_grants(self, assistant_id: int) -> int:
        return int(
            self.db.scalar(
                select(func.count()).select_from(AssistantGrant).where(
                    AssistantGrant.assistant_id == assistant_id,
                    AssistantGrant.grant_status == "valid",
                )
            )
            or 0
        )

    def count_pending_approvals(self, assistant_id: int) -> int:
        return int(
            self.db.scalar(
                select(func.count()).select_from(Approval).where(
                    Approval.assistant_id == assistant_id,
                    Approval.status == "pending",
                )
            )
            or 0
        )

    def invalidate_grants(self, assistant_id: int) -> int:
        rows = self.db.scalars(
            select(AssistantGrant).where(
                AssistantGrant.assistant_id == assistant_id,
                AssistantGrant.grant_status == "valid",
            )
        ).all()
        for row in rows:
            row.grant_status = "invalid"
            row.updated_at = datetime.now()
        return len(rows)

    def terminate_pending_approvals(self, assistant_id: int) -> int:
        rows = self.db.scalars(
            select(Approval).where(
                Approval.assistant_id == assistant_id,
                Approval.status == "pending",
            )
        ).all()
        for row in rows:
            row.status = "terminated"
            row.updated_at = datetime.now()
        return len(rows)
