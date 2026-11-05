"""范围选择路由（对应 docs/03 接口 14 ~ 18）。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.pagination import PageParams
from app.core.response import ok
from app.core.security import CurrentUser, get_current_user
from app.schemas.scope import (
    OrgTreeResponse,
    RoleListResponse,
    RoleOut,
    ScopeExpandResult,
    ScopePayload,
    UserListResponse,
    UserOut,
)
from app.services import master_data
from app.services.scope_service import ScopeService

router = APIRouter(prefix="/scopes", tags=["scopes"])


@router.get("/org-tree", summary="组织树")
def org_tree(
    keyword: str | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    tree = master_data.search_org_tree(keyword)
    return ok(OrgTreeResponse.model_validate({"tree": tree}).model_dump(by_alias=True))


@router.get("/roles", summary="角色列表")
def roles(user: CurrentUser = Depends(get_current_user)) -> dict:
    payload = RoleListResponse(
        list=[RoleOut(id=r.id, name=r.name, desc=r.desc) for r in master_data.ROLES]
    )
    return ok(payload.model_dump(by_alias=True))


@router.get("/positions", summary="岗位列表")
def positions(user: CurrentUser = Depends(get_current_user)) -> dict:
    payload = RoleListResponse(
        list=[RoleOut(id=p.id, name=p.name, desc=p.desc) for p in master_data.POSITIONS]
    )
    return ok(payload.model_dump(by_alias=True))


@router.get("/users", summary="人员搜索")
def users(
    keyword: str | None = Query(default=None),
    orgIds: str | None = Query(default=None),  # noqa: N803 - 与前端参数名一致
    paging: PageParams = Depends(),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    org_id_list = [item for item in (orgIds or "").split(",") if item.strip()]
    matched = master_data.search_employees(keyword=keyword, org_ids=org_id_list)
    start = paging.offset
    page_items = matched[start : start + paging.page_size]
    payload = UserListResponse(
        list=[
            UserOut(
                id=e.id,
                name=e.name,
                dept_name=e.dept_name,
                job_no=e.job_no,
                org_id=e.org_id,
                position_id=e.position_id,
                roles=list(e.roles),
            )
            for e in page_items
        ],
        total=len(matched),
        page=paging.page,
        page_size=paging.page_size,
    )
    return ok(payload.model_dump(by_alias=True))


@router.post("/expand", summary="四维选择展开为人员 + 上限校验")
def expand(
    payload: ScopePayload,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = ScopeService(db)
    result: ScopeExpandResult = service.expand(payload).to_expand_result(payload)
    return ok(result.model_dump(by_alias=True))
