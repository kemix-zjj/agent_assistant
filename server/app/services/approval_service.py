"""审批中心服务（对应 docs/03 §7.1 ~ §7.6）。

决策类接口（通过 / 拒绝）遵循：
- 条件更新保证幂等（受影响行数为 0 时读当前状态）；
- 通过时在同一事务内执行范围生效 + 授权重算 + 状态流转 + 版本记录 + 审计。
"""

import logging
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import (
    BizError,
    ConflictError,
    ErrorCode,
    NotFoundError,
    ParamInvalidError,
)
from app.core.security import CurrentUser
from app.core.timeutils import now_second
from app.models.approval import Approval
from app.models.assistant import Assistant
from app.models.scope import ShareScope
from app.repositories.approval_repo import ApprovalRepository
from app.repositories.assistant_repo import AssistantRepository
from app.schemas.approval import (
    ApprovalAssistantDetail,
    ApprovalCard,
    ApprovalDecisionResult,
    ApprovalDetail,
    ApprovalPage,
    ApprovalScopeResult,
    AssistantAvatar,
    PendingCount,
    ScopeDiff,
    ScopeDiffItem,
)
from app.schemas.scope import ScopePayload
from app.services import audit_service as audit
from app.services.scope_service import ScopeService

logger = logging.getLogger("app.approval")

TYPE_NAME = {"share": "共享申请", "scope_change": "范围变更", "offline": "下架申请"}
VALID_TYPES = {"share", "scope_change"}


def _fmt(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""


class ApprovalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ApprovalRepository(db)
        self.assistants = AssistantRepository(db)
        self.scopes = ScopeService(db)

    # ============================ 列表 ============================

    def list_pending(
        self,
        user: CurrentUser,
        *,
        approval_type: str | None,
        page: int,
        page_size: int,
    ) -> ApprovalPage:
        user.require_admin()
        if approval_type and approval_type not in TYPE_NAME:
            raise ParamInvalidError("approvalType 取值不合法", "approvalType")

        rows, total = self.repo.list_pending(
            company_id=user.company_id,
            approval_type=approval_type,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return ApprovalPage(
            list=[self._to_card(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    def _to_card(self, row: Approval) -> ApprovalCard:
        assistant = row.assistant
        req_payload = (
            self.scopes.payload_of_snapshot(row.requested_scope_id)
            if row.requested_scope_id
            else None
        )
        scope = (
            self.scopes.load_snapshot(row.requested_scope_id)
            if row.requested_scope_id
            else None
        )
        return ApprovalCard(
            approval_id=row.id,
            approval_no=row.approval_no,
            approval_type=row.approval_type,
            approval_type_name=TYPE_NAME.get(row.approval_type, row.approval_type),
            assistant_id=assistant.id,
            assistant_name=assistant.name,
            assistant_avatar=AssistantAvatar(
                type=assistant.avatar_type,
                char=assistant.avatar_char or assistant.name[:1],
                color=assistant.avatar_color,
                url=assistant.avatar_url,
            ),
            assistant_version=row.assistant_version,
            category_name=assistant.category.name if assistant.category else "",
            tags=[tag.name for tag in assistant.tags],
            submitter_name=row.submitter_name,
            submitter_dept=row.submitter_dept,
            submit_time=_fmt(row.submit_time),
            scope_summary=scope.summary if scope else "",
            scope_mode=scope.scope_mode if scope else "RANGE",
            change_note=row.change_note,
        )

    def pending_count(self, user: CurrentUser) -> PendingCount:
        user.require_admin()
        return PendingCount(pending_count=self.repo.count_pending(user.company_id))

    # ============================ 详情 ============================

    def get_detail(self, approval_id: int, user: CurrentUser) -> ApprovalDetail:
        user.require_admin()
        row = self.repo.find(approval_id, user.company_id)
        if row is None:
            raise NotFoundError(ErrorCode.APPROVAL_NOT_FOUND, "审批单不存在")
        if row.status != "pending":
            raise ConflictError(
                ErrorCode.APPROVAL_ALREADY_HANDLED, "该申请已被处理"
            )

        assistant = row.assistant
        adjusted = self._adjusted_scope_id(row.id)
        active_scope_id = adjusted or row.requested_scope_id
        scope = self.scopes.load_snapshot(active_scope_id) if active_scope_id else None

        diff = None
        if adjusted is not None:
            before = (
                self.scopes.payload_of_snapshot(row.requested_scope_id)
                if row.requested_scope_id
                else None
            )
            after = self.scopes.payload_of_snapshot(adjusted)
            if after is not None:
                raw = self.scopes.diff_scope_payloads(before, after)
                diff = ScopeDiff(
                    added_count=raw["addedCount"],
                    removed_count=raw["removedCount"],
                    added=[ScopeDiffItem(**item) for item in raw["added"]],
                    removed=[ScopeDiffItem(**item) for item in raw["removed"]],
                )

        return ApprovalDetail(
            approval_id=row.id,
            approval_no=row.approval_no,
            approval_type=row.approval_type,
            approval_type_name=TYPE_NAME.get(row.approval_type, row.approval_type),
            status=row.status,
            assistant=ApprovalAssistantDetail(
                assistant_id=assistant.id,
                name=assistant.name,
                avatar=AssistantAvatar(
                    type=assistant.avatar_type,
                    char=assistant.avatar_char or assistant.name[:1],
                    color=assistant.avatar_color,
                    url=assistant.avatar_url,
                ),
                description=assistant.description,
                tags=[tag.name for tag in assistant.tags],
                category_name=assistant.category.name if assistant.category else "",
                prompt=assistant.prompt,
                skills=[
                    {"id": s.resource_id, "name": s.resource_name} for s in assistant.skills
                ],
                mcps=[{"id": m.resource_id, "name": m.resource_name} for m in assistant.mcps],
                knowledge_bases=[
                    {"id": k.resource_id, "name": k.resource_name}
                    for k in assistant.knowledge_bases
                ],
                owner_name=assistant.owner_name,
                owner_dept_name=assistant.owner_dept_name,
                version=assistant.version,
            ),
            submitter_name=row.submitter_name,
            submitter_dept=row.submitter_dept,
            submit_time=_fmt(row.submit_time),
            scope_adjusted=adjusted is not None,
            scope=scope,
            scope_diff=diff,
            assistant_config_changed=row.assistant_version != assistant.version,
        )

    def _adjusted_scope_id(self, approval_id: int) -> int | None:
        return self.db.scalar(
            select(ShareScope.id)
            .where(
                ShareScope.approval_id == approval_id,
                ShareScope.stage == "adjusted",
            )
            .order_by(ShareScope.id.desc())
            .limit(1)
        )

    # ============================ 审批前调整范围 ============================

    def adjust_scope(
        self, approval_id: int, payload: ScopePayload, user: CurrentUser
    ) -> ApprovalScopeResult:
        user.require_admin()
        row = self.repo.find(approval_id, user.company_id)
        if row is None:
            raise NotFoundError(ErrorCode.APPROVAL_NOT_FOUND, "审批单不存在")
        if row.status != "pending":
            raise ConflictError(ErrorCode.APPROVAL_ALREADY_HANDLED, "该申请已被处理")

        if payload.scope_mode == "RANGE" and payload.is_empty():
            raise ParamInvalidError("授权范围不可为空，请至少保留一个组织或人员", "scope")
        self.scopes.check_limits(payload)

        # 仅暂存：写 stage=adjusted，不改 requested，不写 assistant_grant
        scope_row = self.scopes.create_snapshot(
            company_id=user.company_id,
            assistant_id=row.assistant_id,
            stage="adjusted",
            payload=payload,
            created_by=user.user_id,
            approval_id=row.id,
        )

        before = (
            self.scopes.payload_of_snapshot(row.requested_scope_id)
            if row.requested_scope_id
            else None
        )
        raw = self.scopes.diff_scope_payloads(before, payload)
        scope = self.scopes.load_snapshot(scope_row.id)
        self.db.commit()
        return ApprovalScopeResult(
            approval_id=row.id,
            scope=scope,
            scope_diff=ScopeDiff(
                added_count=raw["addedCount"],
                removed_count=raw["removedCount"],
                added=[ScopeDiffItem(**item) for item in raw["added"]],
                removed=[ScopeDiffItem(**item) for item in raw["removed"]],
            ),
            scope_adjusted=True,
        )

    # ============================ 审批通过 ============================

    def approve(
        self, approval_id: int, comment: str | None, user: CurrentUser
    ) -> ApprovalDecisionResult:
        user.require_admin()
        now = now_second()

        row = self.repo.find(approval_id, user.company_id)
        if row is None:
            raise NotFoundError(ErrorCode.APPROVAL_NOT_FOUND, "审批单不存在")

        final_scope_id = self._adjusted_scope_id(row.id) or row.requested_scope_id

        # 条件更新保证并发安全；受影响行数为 0 时按当前状态判断是否幂等回放
        # final_scope_id 在下面落 effective 快照后回填，指向真正生效的那张单
        result = self.db.execute(
            update(Approval)
            .where(Approval.id == row.id, Approval.status == "pending")
            .values(
                status="approved",
                approver_id=user.user_id,
                approver_name=user.name,
                approve_time=now,
                change_note=comment or row.change_note,
                updated_at=now,
            )
        )
        if result.rowcount == 0:
            self.db.rollback()
            return self._replay_decision(row.id, user, expected="approved")

        self.db.flush()
        refreshed = self.repo.find(row.id, user.company_id)
        assert refreshed is not None

        assistant = self.assistants.find_by_id(refreshed.assistant_id, user.company_id)
        if assistant is None:
            raise NotFoundError(ErrorCode.ASSISTANT_NOT_FOUND, "助理不存在或已删除")

        payload = (
            self.scopes.payload_of_snapshot(final_scope_id) if final_scope_id else None
        )
        grant_total = 0
        if payload is not None:
            # C-03 / C-08：落一张 effective 快照（明细复制自最终范围），授权名册指向它
            effective = self.scopes.create_snapshot(
                company_id=user.company_id,
                assistant_id=assistant.id,
                stage="effective",
                payload=payload,
                created_by=user.user_id,
                approval_id=row.id,
            )
            refreshed.final_scope_id = effective.id
            grant_total = self.scopes.rebuild_grants(
                assistant, effective.id, payload, now
            )

        assistant.share_status = "approved"
        assistant.last_reject_reason = None
        assistant.last_approver_name = user.name
        assistant.last_approve_time = now
        assistant.version = self._next_minor(assistant.version)
        assistant.updated_at = now

        action = "share_approve" if refreshed.approval_type == "share" else "scope_change"
        self.assistants.add_version_history(
            assistant,
            version=assistant.version,
            action=action,
            operator_id=user.user_id,
            operator_name=user.name,
            remark=comment or f"审批通过，授权 {grant_total} 人",
            created_at=now,
        )
        audit.record(
            self.db,
            user=user,
            action="approval_approve",
            object_type="approval",
            object_id=row.id,
            before={"status": "pending"},
            after={
                "status": "approved",
                "assistantId": assistant.id,
                "finalScopeId": refreshed.final_scope_id,
                "grantTotal": grant_total,
                "comment": comment,
            },
        )
        self.db.commit()

        logger.info(
            "审批通过 approval=%s assistant=%s grant_total=%s",
            row.id,
            assistant.id,
            grant_total,
        )
        return ApprovalDecisionResult(
            approval_id=row.id,
            status="approved",
            assistant_id=assistant.id,
            share_status="approved",
            grant_total=grant_total,
            approve_time=_fmt(now),
        )

    # ============================ 审批拒绝 ============================

    def reject(
        self, approval_id: int, reason: str, user: CurrentUser
    ) -> ApprovalDecisionResult:
        user.require_admin()
        reason = (reason or "").strip()
        if not reason:
            raise BizError(ErrorCode.REJECT_REASON_REQUIRED, "请填写拒绝原因", None, 400)
        if len(reason) > 200:
            raise BizError(
                ErrorCode.REJECT_REASON_TOO_LONG, "原因最多 200 字", None, 400
            )

        now = now_second()
        row = self.repo.find(approval_id, user.company_id)
        if row is None:
            raise NotFoundError(ErrorCode.APPROVAL_NOT_FOUND, "审批单不存在")

        result = self.db.execute(
            update(Approval)
            .where(Approval.id == row.id, Approval.status == "pending")
            .values(
                status="rejected",
                approver_id=user.user_id,
                approver_name=user.name,
                approve_time=now,
                reject_reason=reason,
                updated_at=now,
            )
        )
        if result.rowcount == 0:
            self.db.rollback()
            return self._replay_decision(row.id, user, expected="rejected")

        self.db.flush()
        refreshed = self.repo.find(row.id, user.company_id)
        assert refreshed is not None

        assistant = self.assistants.find_by_id(refreshed.assistant_id, user.company_id)
        if assistant is None:
            raise NotFoundError(ErrorCode.ASSISTANT_NOT_FOUND, "助理不存在或已删除")

        # 拒绝：adjusted 快照保留但不生效，不写 grant
        assistant.share_status = "rejected"
        assistant.last_reject_reason = reason
        assistant.last_approver_name = user.name
        assistant.last_approve_time = now
        assistant.updated_at = now

        self.assistants.add_version_history(
            assistant,
            version=assistant.version,
            action="share_reject",
            operator_id=user.user_id,
            operator_name=user.name,
            remark=reason,
            created_at=now,
        )
        audit.record(
            self.db,
            user=user,
            action="approval_reject",
            object_type="approval",
            object_id=row.id,
            before={"status": "pending"},
            after={
                "status": "rejected",
                "assistantId": assistant.id,
                "rejectReason": reason,
            },
        )
        self.db.commit()

        logger.info("审批拒绝 approval=%s assistant=%s", row.id, assistant.id)
        return ApprovalDecisionResult(
            approval_id=row.id,
            status="rejected",
            assistant_id=assistant.id,
            share_status="rejected",
            reject_reason=reason,
            approve_time=_fmt(now),
        )

    # ============================ 内部工具 ============================

    def _replay_decision(
        self, approval_id: int, user: CurrentUser, expected: str
    ) -> ApprovalDecisionResult:
        """幂等回放：已是目标状态则返回首次结果，否则报已被处理。"""
        row = self.repo.find(approval_id, user.company_id)
        if row is None:
            raise NotFoundError(ErrorCode.APPROVAL_NOT_FOUND, "审批单不存在")
        if row.status != expected:
            raise ConflictError(
                ErrorCode.APPROVAL_ALREADY_HANDLED, "该申请已被处理"
            )

        assistant = self.assistants.find_by_id(row.assistant_id, user.company_id)
        return ApprovalDecisionResult(
            approval_id=row.id,
            status=row.status,  # type: ignore[arg-type]
            assistant_id=row.assistant_id,
            share_status=assistant.share_status if assistant else "unknown",
            grant_total=assistant.authorized_count if assistant else 0,
            reject_reason=row.reject_reason,
            approve_time=_fmt(row.approve_time),
        )

    @staticmethod
    def _next_minor(version: str) -> str:
        try:
            major, minor = version.lstrip("v").split(".")
            return f"v{major}.{int(minor) + 1}"
        except (ValueError, AttributeError):
            return "v1.1"
