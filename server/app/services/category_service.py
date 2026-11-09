"""分类字典服务。"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import (
    ConflictError,
    ErrorCode,
    NoPermissionError,
    NotFoundError,
    ParamInvalidError,
)
from app.core.security import CurrentUser
from app.repositories.category_repo import CategoryRepository
from app.schemas.category import CategoryDeleteResult, CategoryItem


class CategoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CategoryRepository(db)

    def list_categories(self, user: CurrentUser) -> list[CategoryItem]:
        rows = self.repo.list_active(user.company_id)
        return [self._to_item(row) for row in rows]

    def create_category(self, name: str, user: CurrentUser) -> CategoryItem:
        if not user.is_admin:
            raise NoPermissionError("仅公司管理员可新增分类")
        name = self._check_name(name, user)

        row = self.repo.create(user.company_id, name, user.user_id)
        self.db.commit()
        return self._to_item(row)

    def rename_category(self, category_id: int, name: str, user: CurrentUser) -> CategoryItem:
        """重命名分类：分类名下助理随之更新（分类以 ID 关联，无需逐条改）。"""
        if not user.is_admin:
            raise NoPermissionError("仅公司管理员可重命名分类")
        row = self._get_category(category_id, user)
        name = self._check_name(name, user, exclude_id=category_id)

        row.name = name
        self.db.commit()
        return self._to_item(row)

    def delete_category(self, category_id: int, user: CurrentUser) -> CategoryDeleteResult:
        """删除分类：存在助理时拒绝；内置分类同样受分类下助理数量约束。"""
        if not user.is_admin:
            raise NoPermissionError("仅公司管理员可删除分类")
        row = self._get_category(category_id, user)

        count = self.repo.count_assistants(category_id)
        if count > 0:
            raise ConflictError(
                ErrorCode.CATEGORY_IN_USE,
                f"「{row.name}」分类下存在 {count} 个助理，不允许删除",
                {"categoryId": category_id, "assistantCount": count},
            )

        row.deleted_at = datetime.now()
        self.db.commit()
        return CategoryDeleteResult(
            categoryId=category_id, deleted=True, affectedAssistantCount=0
        )

    # ---------------- 内部 ----------------

    @staticmethod
    def _to_item(row) -> CategoryItem:  # noqa: ANN001 - ORM 行对象
        return CategoryItem(
            categoryId=row.id,
            name=row.name,
            isBuiltin=bool(row.is_builtin),
            sortNo=row.sort_no,
        )

    def _get_category(self, category_id: int, user: CurrentUser):  # noqa: ANN202
        row = self.repo.find_by_id(category_id, user.company_id)
        if row is None:
            raise NotFoundError(ErrorCode.CATEGORY_NOT_FOUND, "分类不存在或已删除")
        return row

    def _check_name(
        self, name: str, user: CurrentUser, exclude_id: int | None = None
    ) -> str:
        name = name.strip()
        if not name:
            raise ParamInvalidError("分类名称不能为空", "name")
        if len(name) > 10:
            raise ConflictError(ErrorCode.CATEGORY_NAME_TOO_LONG, "分类名称不超过 10 个字符")

        existed = self.repo.find_by_name(user.company_id, name)
        if existed is not None and existed.id != exclude_id:
            raise ConflictError(
                ErrorCode.CATEGORY_DUPLICATED, "分类名称已存在", {"field": "name"}
            )
        return name
