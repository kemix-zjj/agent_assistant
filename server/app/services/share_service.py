"""共享授权服务：提交共享申请、回显范围、调整范围（对应 docs/03 §6.1 ~ §6.3）。

事务边界：提交共享为单事务，失败整体回滚（文档 Q-09：批量提交整批失败）。
"""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    ErrorCode,
    NoPermissionError,
    NotFoundError,
    ParamInvalidError,
)
from app.core.security import CurrentUser
from app.core.timeutils import now_second
from app.models.approval import Approval
from app.models.assistant import Assistant
from app.models.scope import AssistantGrant, ShareScope
from app.repositories.assistant_repo import AssistantRepository
from app.schemas.scope import (
    Scope,
    ScopePayload,
    ShareScopeResponse,
    ShareScopeUpdatePayload,
    ShareScopeUpdateResult,
    ShareSubmitPayload,
    ShareSubmitResult,
)
from app.services import audit_service as audit
from app.services.scope_service import ScopeService

logger = logging.getLogger("app.share")

MAX_BATCH = 20


def _batch_no() -> str:
    # 单号需完整精度，不能用落库用的秒级时间
    now = datetime.now()
    return f"B{now:%Y%m%d%H%M%S}{now.microsecond:06d}"


def _approval_no(seq: int) -> str:
    """审批单号：AP + 时间戳（含微秒）+ 批次内序号。

    秒级时间戳 + 随机数在同一秒内批量提交时仍可能撞上 uk_approval_no，
    因此用微秒保证唯一（长度 25，适配 VARCHAR(32)）。
    """
    now = datetime.now()
    return f"AP{now:%Y%m%d%H%M%S}{now.microsecond:06d}{seq:02d}"


class ShareService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AssistantRepository(db)
        self.scopes = ScopeService(db)

    # ============================ 提交共享 ============================

    def submit(self, payload: ShareSubmitPayload, user: CurrentUser) -> ShareSubmitResult:
        assistant_ids = payload.assistant_ids
        if not assistant_ids:
            raise ParamInvalidError("请至少选择一个助理", "assistantIds")
        if len(assistant_ids) > MAX_BATCH:
            raise ParamInvalidError(f"单次最多提交 {MAX_BATCH} 个助理", "assistantIds")

        # 1~2. 存在性、公司归属、创建人
        assistants: list[Assistant] = []
        for assistant_id in assistant_ids:
            row = self.repo.find_by_id(assistant_id, user.company_id)
            if row is None:
                raise NotFoundError(
                    ErrorCode.ASSISTANT_NOT_FOUND, "助理不存在或已删除"
                )
            if row.owner_user_id != user.user_id:
                raise NoPermissionError("仅创建人可提交共享申请")
            assistants.append(row)

        # 3. 状态必须为 unshared / rejected
        for row in assistants:
            if row.share_status not in ("unshared", "rejected"):
                raise ConflictError(
                    ErrorCode.ASSISTANT_ALREADY_SHARED,
                    "待审批或已共享的助理不可重复提交",
                    {"assistantId": row.id},
                )

        # 4. 不得存在进行中的审批单（唯一索引兜底）
        for row in assistants:
            if self.repo.count_pending_approvals(row.id) > 0:
                raise ConflictError(
                    ErrorCode.ASSISTANT_STATUS_CHANGED,
                    "所选助理状态已变更，请刷新后重试",
                    {"assistantId": row.id},
                )

        # 5. 范围校验（非空 + 四维上限）
        if payload.scope.scope_mode == "RANGE" and payload.scope.is_empty():
            raise ParamInvalidError("请至少选择一个组织或人员", "scope")
        self.scopes.check_limits(payload.scope)

        # 6. 展开（主数据不可用时由服务层异常转 INTERNAL_ERROR）
        expanded = self.scopes.expand(payload.scope)

        now = now_second()
        batch_no = _batch_no()
        approval_ids: list[int] = []
        for index, row in enumerate(assistants, start=1):
            # 先建审批单，再建请求范围快照（快照需回填 approval_id）
            approval = Approval(
                approval_no=_approval_no(index),
                batch_no=batch_no,
                company_id=user.company_id,
                approval_type="share",
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

            scope_row = self.scopes.create_snapshot(
                company_id=user.company_id,
                assistant_id=row.id,
                stage="requested",
                payload=payload.scope,
                created_by=user.user_id,
                approval_id=approval.id,
            )
            approval.requested_scope_id = scope_row.id

            old_status = row.share_status
            row.share_status = "pending"
            row.updated_at = now
            self.repo.add_version_history(
                row,
                version=row.version,
                action="share_submit",
                operator_id=user.user_id,
                operator_name=user.name,
                remark=payload.change_note or f"提交共享申请，范围 {expanded.grant_total} 人",
                created_at=now,
            )
            audit.record(
                self.db,
                user=user,
                action="share_submit",
                object_type="assistant",
                object_id=row.id,
                before={"shareStatus": old_status},
                after={
                    "shareStatus": "pending",
                    "approvalId": approval.id,
                    "batchNo": batch_no,
                    "scopeMode": payload.scope.scope_mode,
                    "grantTotal": expanded.grant_total,
                    "scope": payload.scope.model_dump(by_alias=True),
                },
            )
            approval_ids.append(approval.id)

        self.db.commit()
        logger.info(
            "共享申请已提交 batch=%s assistants=%s approvals=%s scope_total=%s",
            batch_no,
            assistant_ids,
            approval_ids,
            expanded.grant_total,
        )
        return ShareSubmitResult(
            batch_no=batch_no,
            approval_ids=approval_ids,
            submitted_count=len(approval_ids),
            assistant_status="pending",
        )

    # ============================ 回显范围 ============================

    def get_share_scope(
        self, assistant_id: int, user: CurrentUser
    ) -> ShareScopeResponse:
        row = self.repo.find_by_id(assistant_id, user.company_id)
        if row is None:
            raise NotFoundError(ErrorCode.ASSISTANT_NOT_FOUND, "助理不存在或已删除")

        # 进行中的范围变更申请
        pending_change = self.db.scalar(
            select(Approval).where(
                Approval.assistant_id == assistant_id,
                Approval.approval_type == "scope_change",
                Approval.status == "pending",
            )
        )

        is_owner = row.owner_user_id == user.user_id
        if user.is_admin:
            editable_by = "direct"
        elif is_owner:
            editable_by = "approval"
        else:
            editable_by = "none"

        # 进行中的范围变更申请存在时，创建人不可再次提交
        editable = editable_by != "none" and pending_change is None

        scope = self._current_effective_scope(assistant_id)
        return ShareScopeResponse(
            assistant_id=assistant_id,
            editable=editable,
            editable_by=editable_by,  # type: ignore[arg-type]
            scope=scope,
            pending_approval_id=pending_change.id if pending_change else None,
        )

    def _current_effective_scope(self, assistant_id: int) -> Scope | None:
        """当前生效范围：优先 effective，其次最近一次的 requested（待审批时回显申请值）。"""
        effective = self.db.scalar(
            select(ShareScope)
            .where(ShareScope.assistant_id == assistant_id, ShareScope.stage == "effective")
            .order_by(ShareScope.id.desc())
            .limit(1)
        )
        if effective is not None:
            return self.scopes.load_snapshot(effective.id)

        requested = self.db.scalar(
            select(ShareScope)
            .where(ShareScope.assistant_id == assistant_id, ShareScope.stage == "requested")
            .order_by(ShareScope.id.desc())
            .limit(1)
        )
        if requested is not None:
            return self.scopes.load_snapshot(requested.id)
        return None

    # ============================ 调整范围 ============================

    def update_share_scope(
        self, assistant_id: int, payload: ShareScopeUpdatePayload, user: CurrentUser
    ) -> ShareScopeUpdateResult:
        row = self.repo.find_by_id(assistant_id, user.company_id)
        if row is None:
            raise NotFoundError(ErrorCode.ASSISTANT_NOT_FOUND, "助理不存在或已删除")

        if payload.scope.scope_mode == "RANGE" and payload.scope.is_empty():
            raise ParamInvalidError("授权范围不可为空，请至少保留一个组织或人员", "scope")
        self.scopes.check_limits(payload.scope)

        is_owner = row.owner_user_id == user.user_id
        if not user.is_admin and not is_owner:
            raise NoPermissionError("无权调整该助理的共享范围")

        # 与进行中的 share 申请并存时不可调整
        if row.share_status == "pending":
            raise ConflictError(
                ErrorCode.SHARE_SCOPE_IMMUTABLE,
                "待审批期间不可修改授权范围",
            )

        now = now_second()

        # 分支 B/C：管理员直接生效（平台预置助理同样走此分支）
        if user.is_admin:
            old_grant_total = row.authorized_count
            scope_row = self.scopes.create_snapshot(
                company_id=user.company_id,
                assistant_id=assistant_id,
                stage="effective",
                payload=payload.scope,
                created_by=user.user_id,
                approval_id=None,
            )
            self._rebuild_grants(row, scope_row, payload.scope, user, now)

            row.version = self._next_minor_version(row.version)
            row.updated_at = now
            self.repo.add_version_history(
                row,
                version=row.version,
                action="scope_change",
                operator_id=user.user_id,
                operator_name=user.name,
                remark=payload.change_note or f"管理员调整授权范围，共 {scope_row.grant_total} 人",
                created_at=now,
            )
            audit.record(
                self.db,
                user=user,
                action="scope_change",
                object_type="assistant",
                object_id=assistant_id,
                before={"scopeMode": None, "scopeId": None, "grantTotal": old_grant_total},
                after={
                    "scopeMode": payload.scope.scope_mode,
                    "scopeId": scope_row.id,
                    "grantTotal": scope_row.grant_total,
                    "scope": payload.scope.model_dump(by_alias=True),
                },
            )
            self.db.commit()
            return ShareScopeUpdateResult(
                assistant_id=assistant_id,
                applied=True,
                approval_id=None,
                scope=self.scopes.load_snapshot(scope_row.id),
            )

        # 分支 A：创建人调整已共享助理 → 提交范围变更审批
        if row.share_status != "approved":
            raise ConflictError(
                ErrorCode.SHARE_SCOPE_IMMUTABLE,
                "仅已共享的助理可提交范围变更",
            )

        pending = self.db.scalar(
            select(Approval).where(
                Approval.assistant_id == assistant_id,
                Approval.approval_type == "scope_change",
                Approval.status == "pending",
            )
        )
        if pending is not None:
            raise ConflictError(
                ErrorCode.SHARE_SCOPE_IMMUTABLE,
                "已存在进行中的范围变更申请",
                {"approvalId": pending.id},
            )

        approval = Approval(
            approval_no=_approval_no(1),
            batch_no=None,
            company_id=user.company_id,
            approval_type="scope_change",
            assistant_id=assistant_id,
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

        scope_row = self.scopes.create_snapshot(
            company_id=user.company_id,
            assistant_id=assistant_id,
            stage="requested",
            payload=payload.scope,
            created_by=user.user_id,
            approval_id=approval.id,
        )
        approval.requested_scope_id = scope_row.id

        self.repo.add_version_history(
            row,
            version=row.version,
            action="scope_change",
            operator_id=user.user_id,
            operator_name=user.name,
            remark=payload.change_note or "提交授权范围变更申请",
            created_at=now,
        )
        self.db.commit()
        return ShareScopeUpdateResult(
            assistant_id=assistant_id,
            applied=False,
            approval_id=approval.id,
            scope=self.scopes.load_snapshot(scope_row.id),
        )

    def _rebuild_grants(
        self,
        row: Assistant,
        scope_row: ShareScope,
        payload: ScopePayload,
        user: CurrentUser,
        now: datetime,
    ) -> None:
        """重算人员级授权（逻辑收敛在 ScopeService，审批通过时复用）。"""
        self.scopes.rebuild_grants(row, scope_row.id, payload, now)

    @staticmethod
    def _next_minor_version(version: str) -> str:
        try:
            major, minor = version.lstrip("v").split(".")
            return f"v{major}.{int(minor) + 1}"
        except (ValueError, AttributeError):
            return "v1.1"
