"""审计日志写入（对应 docs/02 4.14 与 docs/03 §6.1 / §7.5 副作用）。"""

import logging

from sqlalchemy.orm import Session

from app.core.security import CurrentUser
from app.models.system import SysAuditLog

logger = logging.getLogger("app.audit")


def record(
    db: Session,
    *,
    user: CurrentUser,
    action: str,
    object_type: str,
    object_id: int | str | None,
    before: dict | None = None,
    after: dict | None = None,
    client_ip: str | None = None,
) -> None:
    """写一条审计记录。审计失败不阻断主流程，仅记日志。"""
    try:
        db.add(
            SysAuditLog(
                company_id=user.company_id,
                operator_id=user.user_id,
                operator_name=user.name,
                action=action,
                object_type=object_type,
                object_id=str(object_id) if object_id is not None else None,
                before_value=before,
                after_value=after,
                client_ip=client_ip,
            )
        )
    except Exception as exc:  # noqa: BLE001 - 审计不能影响主流程
        logger.warning("审计写入失败 action=%s object=%s: %s", action, object_type, exc)
