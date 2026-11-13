"""助理领域服务：列表、详情、创建、编辑、删除（对应 docs/03 §3.1 ~ §3.6）。"""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import (
    BizError,
    ConflictError,
    ErrorCode,
    NotFoundError,
    NoPermissionError,
    ParamInvalidError,
)
from app.core.security import CurrentUser
from app.core.timeutils import now_second
from app.models.approval import Approval
from app.models.assistant import Assistant
from app.models.scope import AssistantGrant, ShareScope
from app.repositories.assistant_repo import AssistantRepository
from app.repositories.category_repo import CategoryRepository
from app.schemas.assistant import (
    AssistantCard,
    AssistantDetail,
    AssistantPage,
    AssistantUpsertPayload,
    DeleteImpact,
    DeleteResult,
    KnowledgeBaseRef,
    McpRef,
    ResourceRef,
    SharedFrom,
    VersionHistoryItem,
)
from app.services import resource_catalog
from app.services import master_data
from app.services import audit_service as audit
from app.services.numbering import approval_no
from app.services.versioning import display_version

logger = logging.getLogger("app.assistant")

VALID_SCOPES = {"all", "mine", "shared"}
VALID_STATUS = {
    "unshared",
    "pending",
    "approved",
    "rejected",
    "offline",
}
VALID_SUBSCRIBE = {"subscribed", "removed"}

# 状态筛选口径：「审批中」统一为 pending，由 pending_type 区分四类审批
PENDING_STATUS = ("pending",)

ACTION_NAME = {
    "create": "创建",
    "update": "编辑更新",
    "share_submit": "提交共享",
    "share_approve": "共享审批通过",
    "share_reject": "共享审批被拒绝",
    "change_submit": "提交变更审批",
    "change_approve": "变更审批通过（内容变更）",
    "change_reject": "变更审批被拒绝",
    "scope_change": "授权范围变更",
    "scope_reject": "授权范围变更被拒绝",
    "offline_submit": "提交下架申请",
    "offline_approve": "下架生效",
    "offline_reject": "下架申请被拒绝",
    "delete": "删除",
}


def _fmt(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def _fmt_required(value: datetime | None) -> str:
    return _fmt(value) or ""


class AssistantService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AssistantRepository(db)
        self.categories = CategoryRepository(db)

    # ============================ 列表 ============================

    def list_assistants(
        self,
        user: CurrentUser,
        *,
        scope: str,
        category_id: int | None,
        keyword: str | None,
        status_filter: str | None,
        subscribe_filter: str | None,
        page: int,
        page_size: int,
    ) -> AssistantPage:
        if scope not in VALID_SCOPES:
            raise ParamInvalidError("scope 取值不合法", "scope")
        if status_filter and status_filter not in VALID_STATUS:
            raise ParamInvalidError("statusFilter 取值不合法", "statusFilter")
        if subscribe_filter and subscribe_filter not in VALID_SUBSCRIBE:
            raise ParamInvalidError("subscribeFilter 取值不合法", "subscribeFilter")

        clean_keyword = keyword.strip() if keyword else None
        if clean_keyword and len(clean_keyword) > 50:
            raise ParamInvalidError("关键词不超过 50 个字符", "keyword")

        ids, total = self.repo.list_ids(
            company_id=user.company_id,
            user_id=user.user_id,
            # 登录账号 → 主数据人员；无映射时共享段为空
            grant_user_id=master_data.employee_id_for_login(user.user_id),
            scope=scope,
            category_id=category_id,
            keyword=clean_keyword,
            status_filter=status_filter if scope == "mine" else None,
            subscribe_filter=subscribe_filter if scope == "shared" else None,
            offset=(page - 1) * page_size,
            limit=page_size,
        )

        rows = self.repo.load_many(ids)
        grants = self.repo.find_grants(
            master_data.employee_id_for_login(user.user_id), ids
        )
        cards = [self._to_card(row, grants.get(row.id), user, scope) for row in rows]

        return AssistantPage(
            list=cards, total=total, page=page, page_size=page_size
        )

    def _to_card(
        self,
        row: Assistant,
        grant: AssistantGrant | None,
        user: CurrentUser,
        scope: str = "all",
    ) -> AssistantCard:
        """卡片字段按「共享视角优先」派生：被授权方看到的 source 为 shared。

        「全部」页签只按三种状态展示：平台内置 / 已共享 / 已订阅，
        审批中与已拒绝的自建助理在该页签一律按「已共享」展示，不带子类角标。
        """
        is_shared = grant is not None and row.owner_user_id != user.user_id
        actions = self._derive_actions(row, grant, user)

        if is_shared:
            return AssistantCard(
                assistant_id=row.id,
                name=row.name,
                avatar_type=row.avatar_type,
                avatar_char=row.avatar_char,
                avatar_url=row.avatar_url,
                avatar_color=row.avatar_color,
                category_id=row.category_id,
                category_name=row.category.name if row.category else "",
                tags=[tag.name for tag in row.tags],
                description=row.description,
                source="shared",
                share_status=None,
                subscribe_status=grant.subscribe_status,
                version=row.version,
                has_shared=True,
                owner_name=row.owner_name,
                owner_title=row.owner_dept_name,
                shared_from=SharedFrom(
                    owner_name=row.owner_name or "", owner_dept_name=row.owner_dept_name
                ),
                authorized_count=0,
                created_at=_fmt_required(row.created_at),
                updated_at=_fmt_required(row.updated_at),
                authorized_at=_fmt(grant.grant_time),
                actions=actions,
            )

        # 「全部」页签：本质已共享的自建 / 第三方助理统一折叠为「已共享」，不展开审批 / 拒绝子类
        collapse = scope == "all"
        collapsed_status = row.share_status
        if collapse and collapsed_status in ("pending", "rejected"):
            collapsed_status = "approved"
        return AssistantCard(
            assistant_id=row.id,
            name=row.name,
            avatar_type=row.avatar_type,
            avatar_char=row.avatar_char,
            avatar_url=row.avatar_url,
            avatar_color=row.avatar_color,
            category_id=row.category_id,
            category_name=row.category.name if row.category else "",
            tags=[tag.name for tag in row.tags],
            description=row.description,
            source=row.source,
            share_status=collapsed_status,
            pending_type=None if collapse else row.pending_type,
            reject_type=None if collapse else row.reject_type,
            subscribe_status=None,
            version=row.version,
            has_shared=bool(row.has_shared),
            owner_name=row.owner_name,
            owner_title=row.owner_dept_name,
            shared_from=None,
            reject_reason=None if collapse else row.last_reject_reason,
            offline_reason=None if collapse else row.offline_reason,
            last_approver_name=row.last_approver_name,
            last_approve_time=_fmt(row.last_approve_time),
            authorized_count=row.authorized_count,
            created_at=_fmt_required(row.created_at),
            updated_at=_fmt_required(row.updated_at),
            actions=actions,
        )

    def _derive_actions(
        self,
        row: Assistant,
        grant: AssistantGrant | None,
        user: CurrentUser,
    ) -> list[str]:
        """按需求 4.0「可执行操作」派生按钮（卡片与详情同源）。"""
        is_owner = row.owner_user_id == user.user_id

        # 被授权方视角
        if grant is not None and not is_owner:
            if grant.grant_status != "valid":
                return []
            if grant.subscribe_status == "subscribed":
                return ["summon", "remove"]
            return ["resubscribe"]

        if row.source == "platform":
            return ["summon", "shareScope"] if user.is_admin else ["summon"]

        if not is_owner:
            # 已下架 / 下架审批中 / 已拒绝仅创建人可召唤
            if row.share_status in ("offline", "rejected") or (
                row.share_status == "pending" and row.pending_type == "offline"
            ):
                return []
            return ["summon"]

        match row.share_status:
            case "unshared":
                return ["summon", "edit", "delete", "share"]
            case "pending":
                # 授权范围 / 下架审批中：原状态继续生效，可查看范围
                if user.is_admin or row.pending_type in ("scope", "offline"):
                    return ["summon", "shareScope"]
                return ["summon"]
            case "approved":
                return ["summon", "edit", "shareScope", "offline"]
            case "rejected":
                # 已拒绝四类均展示「重新提交 / 删除 / 关闭 / 召唤」；
                # 仅「共享审批被拒」真正可删，其余三类点击删除由前端提示不可删除
                return ["summon", "resubmit", "shareScope", "delete"]
            case "offline":
                return ["summon", "edit", "delete", "resubmit"]
            case _:
                return ["summon"]

    # ============================ 详情 ============================

    def get_detail(self, assistant_id: int, user: CurrentUser) -> AssistantDetail:
        row = self.repo.find_by_id(assistant_id, user.company_id)
        if row is None:
            raise NotFoundError(ErrorCode.ASSISTANT_NOT_FOUND, "助理不存在或已删除")

        grant = self.repo.find_grant(
            assistant_id, master_data.employee_id_for_login(user.user_id)
        )
        is_owner = row.owner_user_id == user.user_id
        # 被授权方只读：提示词与能力组成不可见（需求 5.2）
        readonly = grant is not None and not is_owner and not user.is_admin

        detail = AssistantDetail(
            assistant_id=row.id,
            name=row.name,
            avatar_type=row.avatar_type,
            avatar_char=row.avatar_char,
            avatar_url=row.avatar_url,
            avatar_color=row.avatar_color,
            description=row.description,
            tags=[tag.name for tag in row.tags],
            category_id=row.category_id,
            category_name=row.category.name if row.category else "",
            source=row.source,
            share_status=row.share_status,
            pending_type=row.pending_type,
            reject_type=row.reject_type,
            subscribe_status=grant.subscribe_status if grant else None,
            version=row.version,
            has_shared=bool(row.has_shared),
            owner_name=row.owner_name,
            owner_dept_name=row.owner_dept_name,
            reject_reason=row.last_reject_reason,
            offline_reason=row.offline_reason,
            last_approver_name=row.last_approver_name,
            last_approve_time=_fmt(row.last_approve_time),
            created_at=_fmt_required(row.created_at),
            updated_at=_fmt_required(row.updated_at),
            prompt=None if readonly else row.prompt,
            skills=None
            if readonly
            else [ResourceRef(id=s.resource_id, name=s.resource_name) for s in row.skills],
            mcps=None
            if readonly
            else [
                McpRef(id=m.resource_id, name=m.resource_name, type=m.resource_type)
                for m in row.mcps
            ],
            knowledge_bases=None
            if readonly
            else [
                KnowledgeBaseRef(id=k.resource_id, name=k.resource_name)
                for k in row.knowledge_bases
            ],
            quick_questions=[q.content for q in row.quick_questions],
            share_scope=None if readonly else self._current_scope(row.id),
            version_history=[
                VersionHistoryItem(
                    version=item.version,
                    action=item.action,
                    action_name=ACTION_NAME.get(item.action, item.action),
                    operator_name=item.operator_name,
                    remark=item.remark or "",
                    created_at=_fmt_required(item.created_at),
                )
                # 同一秒内可能写入多条，按 (时间, id) 倒序保证最新在前
                for item in sorted(
                    row.version_history,
                    key=lambda h: (h.created_at, h.id or 0),
                    reverse=True,
                )
            ],
            actions=self._derive_actions(row, grant, user),
        )
        return detail

    def _current_scope(self, assistant_id: int) -> dict | None:
        """详情页回显当前范围：effective 优先，其次最近一次 requested（待审批时回显申请值）。"""
        from app.services.scope_service import ScopeService

        for stage in ("effective", "requested"):
            row = self.db.scalar(
                select(ShareScope)
                .where(
                    ShareScope.assistant_id == assistant_id,
                    ShareScope.stage == stage,
                )
                .order_by(ShareScope.id.desc())
                .limit(1)
            )
            if row is None:
                continue
            scope = ScopeService(self.db).load_snapshot(row.id)
            if scope is not None:
                return scope.model_dump(by_alias=True)
        return None

    # ============================ 创建 ============================

    def create_assistant(
        self, payload: AssistantUpsertPayload, user: CurrentUser
    ) -> AssistantDetail:
        self._validate_category(payload.category_id, user)
        if self.repo.find_name_conflict(user.company_id, payload.name) is not None:
            raise ConflictError(
                ErrorCode.ASSISTANT_NAME_DUPLICATED,
                "助理昵称已存在，请修改",
                {"field": "name"},
            )
        skills, mcps, knowledge_bases = self._resolve_resources(payload)

        now = now_second()
        row = self.repo.create(
            company_id=user.company_id,
            name=payload.name,
            avatar_type=payload.avatar_type,
            avatar_char=payload.avatar_char,
            avatar_url=payload.avatar_url,
            avatar_color=payload.avatar_color,
            description=payload.description,
            category_id=payload.category_id,
            source="custom",
            owner_user_id=user.user_id,
            owner_name=user.name,
            owner_dept_name=user.dept_name,
            prompt=payload.prompt,
            share_status="unshared",
            # 未共享不产生版本号，页面展示「未发布」
            version="",
            has_shared=0,
            authorized_count=0,
            created_by=user.user_id,
            created_at=now,
            updated_at=now,
        )
        self.repo.replace_relations(
            row,
            tags=payload.tags,
            quick_questions=payload.quick_questions,
            skills=skills,
            mcps=mcps,
            knowledge_bases=knowledge_bases,
        )
        self.repo.add_version_history(
            row,
            version="未发布",
            action="create",
            operator_id=user.user_id,
            operator_name=user.name,
            remark="手动创建",
            created_at=now,
        )
        self.db.commit()
        return self.get_detail(row.id, user)

    # ============================ 编辑 ============================

    def update_assistant(
        self, assistant_id: int, payload: AssistantUpsertPayload, user: CurrentUser
    ) -> tuple[AssistantDetail, int]:
        """返回详情与受影响授权人数（用于响应头 X-Affected-Grant-Count）。

        需求 4.1.4 编辑规则：
        - 未共享 / 已下架：直接保存生效，不产生版本号、不改变共享状态
        - 已共享过（已共享 / 已拒绝 / 下架审批中）：保存即提交审批，
          审批子类按「是否曾共享过」判别共享审批或调整审批，版本号在审批通过时才推进
        - 审批中（共享 / 调整 / 授权 / 下架审批）：禁止编辑
        """
        row = self.repo.find_by_id(assistant_id, user.company_id)
        if row is None:
            raise NotFoundError(ErrorCode.ASSISTANT_NOT_FOUND, "助理不存在或已删除")
        if row.owner_user_id != user.user_id:
            raise NoPermissionError("非创建人不可编辑该助理")
        if row.share_status in PENDING_STATUS:
            raise ConflictError(
                ErrorCode.SHARE_SCOPE_IMMUTABLE,
                "审批中的助理不可编辑，请等待审批完成",
            )

        self._validate_category(payload.category_id, user)
        if (
            self.repo.find_name_conflict(
                user.company_id, payload.name, exclude_id=assistant_id
            )
            is not None
        ):
            raise ConflictError(
                ErrorCode.ASSISTANT_NAME_DUPLICATED,
                "助理昵称已存在，请修改",
                {"field": "name"},
            )
        skills, mcps, knowledge_bases = self._resolve_resources(payload)

        now = now_second()
        # 已共享过（含已拒绝、下架审批中）的编辑需重新审批；未共享与已下架直接生效
        need_approval = row.share_status in ("approved", "rejected")
        row.name = payload.name
        row.avatar_type = payload.avatar_type
        row.avatar_char = payload.avatar_char
        row.avatar_url = payload.avatar_url
        row.avatar_color = payload.avatar_color
        row.description = payload.description
        row.category_id = payload.category_id
        row.prompt = payload.prompt
        row.updated_at = now

        self.repo.replace_relations(
            row,
            tags=payload.tags,
            quick_questions=payload.quick_questions,
            skills=skills,
            mcps=mcps,
            knowledge_bases=knowledge_bases,
        )

        if not need_approval:
            self.repo.add_version_history(
                row,
                version=display_version(row.version),
                action="update",
                operator_id=user.user_id,
                operator_name=user.name,
                remark="已下架状态下编辑（直接生效）"
                if row.share_status == "offline"
                else "未共享状态下编辑",
                created_at=now,
            )
            affected = self.repo.count_valid_grants(row.id)
            self.db.commit()
            return self.get_detail(row.id, user), affected

        # 已共享过：提交变更审批，审批通过时才生效并推进版本号
        pending_type = "change" if row.has_shared else "share"
        approval = Approval(
            approval_no=approval_no(1),
            batch_no=None,
            company_id=user.company_id,
            approval_type=pending_type,
            assistant_id=row.id,
            assistant_version=row.version,
            status="pending",
            submitter_id=user.user_id,
            submitter_name=user.name,
            submitter_dept=user.dept_name,
            submit_time=now,
            change_note=payload.change_note,
            created_at=now,
            updated_at=now,
        )
        self.db.add(approval)
        self.db.flush()

        row.share_status = "pending"
        row.pending_type = pending_type
        row.reject_type = None
        row.last_reject_reason = None
        self.repo.add_version_history(
            row,
            version=display_version(row.version),
            action="change_submit",
            operator_id=user.user_id,
            operator_name=user.name,
            remark=payload.change_note or "提交变更审批",
            created_at=now,
        )
        audit.record(
            self.db,
            user=user,
            action="assistant_update",
            object_type="assistant",
            object_id=row.id,
            before={"shareStatus": "approved" if row.has_shared else "rejected"},
            after={"shareStatus": "pending", "pendingType": pending_type, "approvalId": approval.id},
        )
        self.db.commit()
        return self.get_detail(row.id, user), 0

    # ============================ 删除 ============================

    def get_delete_impact(self, assistant_id: int, user: CurrentUser) -> DeleteImpact:
        row = self.repo.find_by_id(assistant_id, user.company_id)
        if row is None:
            raise NotFoundError(ErrorCode.ASSISTANT_NOT_FOUND, "助理不存在或已删除")
        return DeleteImpact(
            assistant_id=row.id,
            name=row.name,
            authorized_count=self.repo.count_valid_grants(row.id),
            pending_apply_count=self.repo.count_pending_approvals(row.id),
        )

    def delete_assistant(self, assistant_id: int, user: CurrentUser) -> DeleteResult:
        """删除规则（需求 4.1.5）：

        - 未共享 / 已下架：允许删除
        - 已拒绝 · 共享审批（从未共享过）：允许删除，配置、版本记录与审批记录一并清除
        - 已拒绝 · 调整 / 授权 / 下架审批（曾共享过）：不允许删除，须走下架处理
        - 已共享 / 审批中：不提供删除入口（接口同样拒绝）
        """
        row = self.repo.find_by_id(assistant_id, user.company_id)
        if row is None:
            raise NotFoundError(ErrorCode.ASSISTANT_NOT_FOUND, "助理不存在或已删除")
        if row.owner_user_id != user.user_id:
            raise NoPermissionError("非创建人不可删除该助理")
        if row.share_status == "rejected" and (row.reject_type != "share" or row.has_shared):
            raise ConflictError(
                ErrorCode.ASSISTANT_ALREADY_SHARED,
                "该助理已共享过，无法删除，请进行下架处理",
            )
        if row.share_status in ("approved", "pending"):
            raise ConflictError(
                ErrorCode.ASSISTANT_ALREADY_SHARED,
                "该助理已共享或审批中，无法删除，请进行下架处理",
            )

        now = now_second()
        # 单事务：逻辑删除 → 授权失效 → 待审批终止 → 版本记录 + 审计
        row.deleted_at = now
        row.updated_at = now

        invalidated = self.repo.invalidate_grants(row.id)
        terminated = self.repo.terminate_pending_approvals(row.id)

        self.repo.add_version_history(
            row,
            version=display_version(row.version),
            action="delete",
            operator_id=user.user_id,
            operator_name=user.name,
            remark=f"删除助理，失效授权 {invalidated} 条、终止审批 {terminated} 条",
            created_at=now,
        )
        self.db.commit()
        logger.info(
            "助理已删除 assistant_id=%s invalidated=%s terminated=%s",
            row.id,
            invalidated,
            terminated,
        )
        return DeleteResult(assistant_id=row.id, deleted=True)

    # ============================ 校验 ============================

    def _validate_category(self, category_id: int, user: CurrentUser) -> None:
        exists = any(
            item.id == category_id for item in self.categories.list_active(user.company_id)
        )
        if not exists:
            raise ParamInvalidError("所属分类不存在", "categoryId")

    def _resolve_resources(
        self, payload: AssistantUpsertPayload
    ) -> tuple[list[tuple[str, str]], list[tuple[str, str, str | None]], list[tuple[str, str]]]:
        """校验资源可用性并生成落库快照（ID + 名称）。"""
        missing_skills = resource_catalog.missing_skill_ids(payload.skill_ids)
        if missing_skills:
            raise ConflictError(
                ErrorCode.RESOURCE_UNAVAILABLE,
                "所选 SKILL 已不可用，请重新选择",
                {"field": "skillIds", "missing": missing_skills},
            )
        missing_mcps = resource_catalog.missing_mcp_ids(payload.mcp_ids)
        if missing_mcps:
            raise ConflictError(
                ErrorCode.RESOURCE_UNAVAILABLE,
                "所选 MCP 已不可用，请重新选择",
                {"field": "mcpIds", "missing": missing_mcps},
            )
        missing_kbs = resource_catalog.missing_kb_ids(payload.knowledge_base_ids)
        if missing_kbs:
            raise ConflictError(
                ErrorCode.KB_NO_PERMISSION,
                "所选知识库无访问权限",
                {"field": "knowledgeBaseIds", "missing": missing_kbs},
            )

        skills = [
            (item.id, item.name)
            for item in resource_catalog.find_skills(payload.skill_ids)
        ]
        mcps = [
            (item.id, item.name, item.type)
            for item in resource_catalog.find_mcps(payload.mcp_ids)
        ]
        knowledge_bases = [
            (item.id, item.name)
            for item in resource_catalog.find_knowledge_bases(payload.knowledge_base_ids)
        ]
        return skills, mcps, knowledge_bases


def ensure_assistant_exists(row: Assistant | None) -> Assistant:
    if row is None:
        raise BizError(ErrorCode.ASSISTANT_NOT_FOUND, "助理不存在或已删除", None, 404)
    return row
