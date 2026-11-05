"""分类字典服务。"""

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ErrorCode, NoPermissionError, ParamInvalidError
from app.core.security import CurrentUser
from app.models.assistant import AssistantCategory
from app.repositories.category_repo import CategoryRepository
from app.schemas.category import CategoryItem


class CategoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CategoryRepository(db)

    def list_categories(self, user: CurrentUser) -> list[CategoryItem]:
        rows = self.repo.list_active(user.company_id)
        return [
            CategoryItem(
                categoryId=row.id,
                name=row.name,
                isBuiltin=bool(row.is_builtin),
                sortNo=row.sort_no,
            )
            for row in rows
        ]

    def create_category(self, name: str, user: CurrentUser) -> CategoryItem:
        if not user.is_admin:
            raise NoPermissionError("仅公司管理员可新增分类")

        name = name.strip()
        if not name:
            raise ParamInvalidError("分类名称不能为空", "name")
        if len(name) > 10:
            raise ConflictError(ErrorCode.CATEGORY_NAME_TOO_LONG, "分类名称不超过 10 个字符")

        if self.repo.find_by_name(user.company_id, name) is not None:
            raise ConflictError(
                ErrorCode.CATEGORY_DUPLICATED, "分类名称已存在", {"field": "name"}
            )

        row = self.repo.create(user.company_id, name, user.user_id)
        self.db.commit()
        return CategoryItem(
            categoryId=row.id,
            name=row.name,
            isBuiltin=bool(row.is_builtin),
            sortNo=row.sort_no,
        )
