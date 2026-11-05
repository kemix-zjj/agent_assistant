"""分类字典数据访问层。"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assistant import AssistantCategory


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active(self, company_id: int) -> list[AssistantCategory]:
        stmt = (
            select(AssistantCategory)
            .where(
                AssistantCategory.company_id == company_id,
                AssistantCategory.deleted_at.is_(None),
            )
            .order_by(AssistantCategory.sort_no.asc(), AssistantCategory.id.asc())
        )
        return list(self.db.scalars(stmt))

    def find_by_name(self, company_id: int, name: str) -> AssistantCategory | None:
        stmt = select(AssistantCategory).where(
            AssistantCategory.company_id == company_id,
            AssistantCategory.name == name,
            AssistantCategory.deleted_at.is_(None),
        )
        return self.db.scalar(stmt)

    def create(self, company_id: int, name: str, created_by: int) -> AssistantCategory:
        max_sort = self.db.scalar(
            select(AssistantCategory.sort_no)
            .where(AssistantCategory.company_id == company_id)
            .order_by(AssistantCategory.sort_no.desc())
            .limit(1)
        )
        row = AssistantCategory(
            company_id=company_id,
            name=name,
            sort_no=(max_sort or 0) + 10,
            is_builtin=0,
            created_by=created_by,
            created_at=datetime.now(),
        )
        self.db.add(row)
        self.db.flush()
        return row
