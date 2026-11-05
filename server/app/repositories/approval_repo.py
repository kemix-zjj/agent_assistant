"""审批单数据访问层。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.approval import Approval
from app.models.assistant import Assistant

_EAGER = (
    selectinload(Approval.assistant).selectinload(Assistant.category),
    selectinload(Approval.assistant).selectinload(Assistant.tags),
    selectinload(Approval.assistant).selectinload(Assistant.skills),
    selectinload(Approval.assistant).selectinload(Assistant.mcps),
    selectinload(Approval.assistant).selectinload(Assistant.knowledge_bases),
)


class ApprovalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_pending(
        self,
        *,
        company_id: int,
        approval_type: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Approval], int]:
        conditions = [Approval.company_id == company_id, Approval.status == "pending"]
        if approval_type:
            conditions.append(Approval.approval_type == approval_type)

        total = int(
            self.db.scalar(select(func.count()).select_from(Approval).where(*conditions)) or 0
        )
        rows = self.db.scalars(
            select(Approval)
            .options(*_EAGER)
            .where(*conditions)
            # 等待最久优先
            .order_by(Approval.submit_time.asc(), Approval.id.asc())
            .offset(offset)
            .limit(limit)
        ).all()
        return list(rows), total

    def count_pending(self, company_id: int) -> int:
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(Approval)
                .where(Approval.company_id == company_id, Approval.status == "pending")
            )
            or 0
        )

    def find(self, approval_id: int, company_id: int) -> Approval | None:
        return self.db.scalar(
            select(Approval)
            .options(*_EAGER)
            # 决策走了 UPDATE 语句，需强制刷新身份映射中的旧对象
            .execution_options(populate_existing=True)
            .where(Approval.id == approval_id, Approval.company_id == company_id)
        )

    def find_pending(self, approval_id: int, company_id: int) -> Approval | None:
        return self.db.scalar(
            select(Approval)
            .options(*_EAGER)
            .execution_options(populate_existing=True)
            .where(
                Approval.id == approval_id,
                Approval.company_id == company_id,
                Approval.status == "pending",
            )
        )
