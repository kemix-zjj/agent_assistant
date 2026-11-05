"""资源候选列表路由（对应 docs/03 接口 11 ~ 13）。"""

from fastapi import APIRouter, Depends, Query

from app.core.errors import ParamInvalidError
from app.core.response import ok
from app.core.security import CurrentUser, get_current_user
from app.schemas.common import (
    KnowledgeBaseListResponse,
    McpListResponse,
    SkillListResponse,
)
from app.services import resource_service

router = APIRouter(prefix="/resources", tags=["resources"])


def _check_keyword(keyword: str | None) -> str | None:
    if keyword and len(keyword) > 50:
        raise ParamInvalidError("关键词不超过 50 个字符", "keyword")
    return keyword


@router.get("/skills", summary="可挂载 SKILL 列表")
def list_skills(
    keyword: str | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    payload = SkillListResponse(list=resource_service.list_skills(_check_keyword(keyword)))
    return ok(payload.model_dump(by_alias=True))


@router.get("/mcps", summary="可挂载 MCP 列表")
def list_mcps(
    keyword: str | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    payload = McpListResponse(list=resource_service.list_mcps(_check_keyword(keyword)))
    return ok(payload.model_dump(by_alias=True))


@router.get("/knowledge-bases", summary="可访问知识库列表")
def list_knowledge_bases(
    keyword: str | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    payload = KnowledgeBaseListResponse(
        list=resource_service.list_knowledge_bases(_check_keyword(keyword))
    )
    return ok(payload.model_dump(by_alias=True))
