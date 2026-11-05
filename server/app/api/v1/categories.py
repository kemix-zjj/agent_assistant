"""分类字典路由（对应 docs/03 接口 9、10）。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import ok
from app.core.security import CurrentUser, get_current_user
from app.schemas.category import CategoryCreatePayload, CategoryListResponse
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", summary="分类字典")
def list_categories(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = CategoryService(db)
    result = CategoryListResponse(list=service.list_categories(user))
    return ok(result.model_dump())


@router.post("", summary="新增分类（仅管理员）")
def create_category(
    payload: CategoryCreatePayload,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    service = CategoryService(db)
    item = service.create_category(payload.name, user)
    return ok(item.model_dump())
