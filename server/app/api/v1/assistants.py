"""助理路由（对应 docs/03 接口 1 ~ 8）。"""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.pagination import PageParams
from app.core.response import ok
from app.core.security import CurrentUser, get_current_user
from app.schemas.assistant import AssistantUpsertPayload
from app.schemas.common import SubscriptionPayload, SummonPayload
from app.services.assistant_service import AssistantService
from app.services.summon_service import SummonService

router = APIRouter(prefix="/assistants", tags=["assistants"])


@router.get("", summary="助理团助理列表")
def list_assistants(
    response: Response,
    scope: str = Query(default="all", description="all / mine / shared"),
    categoryId: int | None = Query(default=None),  # noqa: N803 - 保持前端参数名
    keyword: str | None = Query(default=None),
    statusFilter: str | None = Query(default=None),  # noqa: N803
    subscribeFilter: str | None = Query(default=None),  # noqa: N803
    paging: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = AssistantService(db)
    page = service.list_assistants(
        user,
        scope=scope,
        category_id=categoryId,
        keyword=keyword,
        status_filter=statusFilter,
        subscribe_filter=subscribeFilter,
        page=paging.page,
        page_size=paging.page_size,
    )
    return ok(page.model_dump(by_alias=True))


@router.get("/{assistantId}", summary="助理详情")
def get_assistant(
    assistantId: int,  # noqa: N803 - 路径参数名与文档一致
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = AssistantService(db)
    detail = service.get_detail(assistantId, user)
    return ok(detail.model_dump(by_alias=True))


@router.post("/{assistantId}/summon", summary="召唤助理")
def summon_assistant(
    assistantId: int,  # noqa: N803
    payload: SummonPayload,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = SummonService(db)
    result = service.summon(assistantId, payload.source, user)
    return ok(result.model_dump(by_alias=True))


@router.put("/{assistantId}/subscription", summary="移除 / 重新订阅共享助理")
def update_subscription(
    assistantId: int,  # noqa: N803
    payload: SubscriptionPayload,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = SummonService(db)
    result = service.update_subscription(assistantId, payload.action, user)
    return ok(result.model_dump(by_alias=True))


@router.post("", summary="手动创建助理", status_code=status.HTTP_201_CREATED)
def create_assistant(
    payload: AssistantUpsertPayload,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = AssistantService(db)
    detail = service.create_assistant(payload, user)
    return ok(detail.model_dump(by_alias=True))


@router.put("/{assistantId}", summary="编辑助理")
def update_assistant(
    assistantId: int,  # noqa: N803
    payload: AssistantUpsertPayload,
    response: Response,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = AssistantService(db)
    detail, affected = service.update_assistant(assistantId, payload, user)
    # 已共享时前端据此展示「变更将立即对 N 个授权对象生效」
    if affected:
        response.headers["X-Affected-Grant-Count"] = str(affected)
    return ok(detail.model_dump(by_alias=True))


@router.get("/{assistantId}/delete-impact", summary="删除影响面")
def delete_impact(
    assistantId: int,  # noqa: N803
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = AssistantService(db)
    impact = service.get_delete_impact(assistantId, user)
    return ok(impact.model_dump(by_alias=True))


@router.delete("/{assistantId}", summary="删除助理")
def delete_assistant(
    assistantId: int,  # noqa: N803
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = AssistantService(db)
    result = service.delete_assistant(assistantId, user)
    return ok(result.model_dump(by_alias=True))
