"""助理召唤与订阅服务（对应 docs/03 §3.7 / §3.8）。"""

import logging
import random
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
from app.core.timeutils import now_second
from app.models.assistant import Assistant
from app.models.system import AssistantSummon
from app.repositories.assistant_repo import AssistantRepository
from app.schemas.common import (
    SubscriptionResult,
    SummonAvatar,
    SummonResult,
)
from app.services import audit_service as audit
from app.services import master_data

logger = logging.getLogger("app.summon")


def _session_id() -> str:
    now = datetime.now()
    return f"S{now:%Y%m%d%H%M%S}{random.randint(100, 999)}"


class SummonService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AssistantRepository(db)

    def summon(
        self, assistant_id: int, source: str, user: CurrentUser
    ) -> SummonResult:
        row = self.repo.find_by_id(assistant_id, user.company_id)
        if row is None:
            raise NotFoundError(ErrorCode.ASSISTANT_NOT_FOUND, "助理不存在或已删除")

        self._ensure_available(row, user)

        now = now_second()
        session_id = _session_id()
        title = f"召唤 {row.name}"
        self.db.add(
            AssistantSummon(
                company_id=user.company_id,
                assistant_id=row.id,
                user_id=user.user_id,
                session_id=session_id,
                session_title=title,
                created_at=now,
            )
        )
        # 召唤不改助理配置（REQ-EXP-SUMMON-008）
        audit.record(
            self.db,
            user=user,
            action="assistant_summon",
            object_type="assistant",
            object_id=row.id,
            after={"sessionId": session_id, "source": source},
        )
        self.db.commit()

        logger.info("召唤助理 assistant=%s session=%s", row.id, session_id)
        return SummonResult(
            session_id=session_id,
            session_title=title,
            assistant_id=row.id,
            assistant_name=row.name,
            assistant_avatar=SummonAvatar(
                type=row.avatar_type,
                char=row.avatar_char or row.name[:1],
                color=row.avatar_color,
                url=row.avatar_url,
            ),
            quick_questions=[q.content for q in row.quick_questions],
            created_at=now.strftime("%Y-%m-%d %H:%M:%S"),
        )

    def _ensure_available(self, row: Assistant, user: CurrentUser) -> None:
        """可用性：平台预置恒可用；自建需为创建人；共享需授权有效且已订阅。"""
        if row.source == "platform":
            return

        if row.owner_user_id == user.user_id:
            return

        grant = self.repo.find_grant(
            row.id, master_data.employee_id_for_login(user.user_id)
        )
        if grant is None or grant.grant_status != "valid":
            raise NoPermissionError("无权使用该助理")
        if grant.subscribe_status != "subscribed":
            raise ConflictError(
                ErrorCode.ASSISTANT_NOT_AVAILABLE, "该助理已被移除，请先重新订阅"
            )

    # ============================ 订阅 ============================

    def update_subscription(
        self, assistant_id: int, action: str, user: CurrentUser
    ) -> SubscriptionResult:
        if action not in ("remove", "resubscribe"):
            raise ParamInvalidError("action 取值不合法", "action")

        row = self.repo.find_by_id(assistant_id, user.company_id)
        if row is None:
            raise NotFoundError(ErrorCode.ASSISTANT_NOT_FOUND, "助理不存在或已删除")

        employee_id = master_data.employee_id_for_login(user.user_id)
        grant = self.repo.find_grant(row.id, employee_id)
        if grant is None or grant.grant_status != "valid":
            raise ConflictError(ErrorCode.GRANT_INVALID, "该助理授权已失效")

        now = datetime.now()
        if action == "remove":
            if grant.subscribe_status == "removed":
                # 幂等：重复移除直接返回当前状态
                return SubscriptionResult(
                    assistant_id=row.id,
                    subscribe_status=grant.subscribe_status,
                    subscribe_time=grant.subscribe_time.strftime("%Y-%m-%d %H:%M:%S"),
                )
            grant.subscribe_status = "removed"
        else:
            if grant.subscribe_status == "subscribed":
                return SubscriptionResult(
                    assistant_id=row.id,
                    subscribe_status=grant.subscribe_status,
                    subscribe_time=grant.subscribe_time.strftime("%Y-%m-%d %H:%M:%S"),
                )
            grant.subscribe_status = "subscribed"

        # 只改订阅状态，不触碰 grant_status / share_scope / 创建人侧 share_status。
        # DATETIME 精度为秒，落库前截断微秒，避免库内值与响应值差 1 秒。
        now = now_second()
        grant.subscribe_time = now
        grant.updated_at = now
        audit.record(
            self.db,
            user=user,
            action="grant_remove" if action == "remove" else "grant_resubscribe",
            object_type="grant",
            object_id=grant.id,
            before={"subscribeStatus": "subscribed" if action == "remove" else "removed"},
            after={"subscribeStatus": grant.subscribe_status, "assistantId": row.id},
        )
        self.db.commit()

        logger.info(
            "订阅状态变更 assistant=%s user=%s action=%s", row.id, employee_id, action
        )
        return SubscriptionResult(
            assistant_id=row.id,
            subscribe_status=grant.subscribe_status,
            subscribe_time=now.strftime("%Y-%m-%d %H:%M:%S"),
        )
