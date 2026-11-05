"""共享审批路由（对应 docs/03 接口 22 ~ 27）。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.pagination import PageParams
from app.core.response import ok
from app.core.security import CurrentUser, get_current_user
from app.schemas.approval import ApprovalScopePayload, ApprovePayload, RejectPayload
from app.services.approval_service import ApprovalService

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", summary="待审批列表")
def list_approvals(
    approvalType: str | None = Query(default=None),  # noqa: N803
    paging: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = ApprovalService(db)
    page = service.list_pending(
        user,
        approval_type=approvalType,
        page=paging.page,
        page_size=paging.page_size,
    )
    return ok(page.model_dump(by_alias=True))


@router.get("/pending-count", summary="待审批数量角标")
def pending_count(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = ApprovalService(db)
    return ok(service.pending_count(user).model_dump(by_alias=True))


@router.get("/{approvalId}", summary="审批详情")
def get_approval(
    approvalId: int,  # noqa: N803
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = ApprovalService(db)
    detail = service.get_detail(approvalId, user)
    return ok(detail.model_dump(by_alias=True))


@router.put("/{approvalId}/scope", summary="审批前调整授权范围（暂存）")
def adjust_approval_scope(
    approvalId: int,  # noqa: N803
    payload: ApprovalScopePayload,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = ApprovalService(db)
    result = service.adjust_scope(approvalId, payload.scope, user)
    return ok(result.model_dump(by_alias=True))


@router.post("/{approvalId}/approve", summary="审批通过")
def approve(
    approvalId: int,  # noqa: N803
    payload: ApprovePayload,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = ApprovalService(db)
    result = service.approve(approvalId, payload.comment, user)
    body = result.model_dump(by_alias=True)
    db.commit()
    return ok(body)


@router.post("/{approvalId}/reject", summary="审批拒绝")
def reject(
    approvalId: int,  # noqa: N803
    payload: RejectPayload,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = ApprovalService(db)
    result = service.reject(approvalId, payload.reject_reason, user)
    body = result.model_dump(by_alias=True)
    db.commit()
    return ok(body)
