"""共享授权路由（对应 docs/03 接口 19 ~ 21）。

注意：/assistants/{id}/share-scope 与助理路由同前缀，需在校验顺序上避免
与 /assistants/{id} 冲突（FastAPI 按注册顺序匹配，本路由先于详情注册）。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import ok
from app.core.security import CurrentUser, get_current_user
from app.schemas.scope import ShareScopeUpdatePayload, ShareSubmitPayload
from app.services.share_service import ShareService

router = APIRouter(tags=["shares"])


@router.post("/shares", summary="提交共享申请", status_code=status.HTTP_201_CREATED)
def submit_share(
    payload: ShareSubmitPayload,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = ShareService(db)
    result = service.submit(payload, user)
    return ok(result.model_dump(by_alias=True))


@router.get("/assistants/{assistantId}/share-scope", summary="回显当前共享范围")
def get_share_scope(
    assistantId: int,  # noqa: N803
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = ShareService(db)
    result = service.get_share_scope(assistantId, user)
    return ok(result.model_dump(by_alias=True))


@router.put("/assistants/{assistantId}/share-scope", summary="调整共享范围")
def update_share_scope(
    assistantId: int,  # noqa: N803
    payload: ShareScopeUpdatePayload,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = ShareService(db)
    result = service.update_share_scope(assistantId, payload, user)
    return ok(result.model_dump(by_alias=True))
