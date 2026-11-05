"""AI 生成路由（对应 docs/03 接口 28）。"""

from fastapi import APIRouter, Depends

from app.core.response import ok
from app.core.security import CurrentUser, get_current_user
from app.schemas.common import AiGeneratePayload
from app.services.ai_service import AiGenerateService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/generate", summary="AI 生成 / 润色（四字段统一）")
def generate(
    payload: AiGeneratePayload,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    result = AiGenerateService().generate(payload)
    return ok(result.model_dump(by_alias=True))
