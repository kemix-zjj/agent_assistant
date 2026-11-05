"""幂等键支持（对应 docs/03-接口设计 §1 幂等约定 + sys_idempotency 表）。

审批决策与订阅操作读 Header `Idempotency-Key`：
首次请求落库并返回结果，后续相同 key 直接回放首次响应。
"""

import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.system import SysIdempotency

IDEMPOTENCY_TTL_HOURS = 24


def replay_if_hit(db: Session, key: str | None, biz_type: str) -> dict | None:
    """命中返回首次响应体；未命中返回 None。"""
    if not key:
        return None
    row = db.scalar(
        select(SysIdempotency).where(
            SysIdempotency.idempotency_key == key,
            SysIdempotency.biz_type == biz_type,
        )
    )
    if row is None:
        return None
    if row.response_body is None:
        return None
    return row.response_body


def save_result(
    db: Session, key: str | None, biz_type: str, biz_id: str | None, payload: object
) -> None:
    """落库首次响应。并发下唯一键冲突视为已存在，直接忽略。"""
    if not key:
        return
    now = datetime.now()
    row = SysIdempotency(
        idempotency_key=key,
        biz_type=biz_type,
        biz_id=biz_id,
        response_body=json.loads(json.dumps(payload, default=str)),
        created_at=now,
        expired_at=now + timedelta(hours=IDEMPOTENCY_TTL_HOURS),
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
