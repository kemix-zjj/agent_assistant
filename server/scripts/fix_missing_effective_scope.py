"""一次性维护：为「已通过但缺少 effective 快照」的历史审批单补齐生效范围。

背景：早期版本的 approve() 只重算 assistant_grant，跳过了写 share_scope(stage=effective)
这一步（违反 docs/02 C-03 / C-08），导致已通过审批的助理缺少生效范围记录、
approval.final_scope_id 指向 requested/adjusted、grant.source_scope_id 也指向非生效单。

本脚本按审批单逐一补：
1. 以 final_scope_id（无则 requested_scope_id）为源，新建 stage=effective 快照（含明细复制）；
2. approval.final_scope_id 指向新快照；
3. 按新快照重算 assistant_grant，source_scope_id 与 authorized_count 一并纠正。

幂等：已存在 stage=effective 快照的助理直接跳过，可重复执行。
"""

import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.core.timeutils import now_second  # noqa: E402
from app.models.approval import Approval  # noqa: E402
from app.models.assistant import Assistant  # noqa: E402
from app.models.scope import ShareScope  # noqa: E402
from app.services.scope_service import ScopeService  # noqa: E402


def _has_effective(db, assistant_id: int) -> bool:
    return (
        db.scalar(
            select(ShareScope.id)
            .where(
                ShareScope.assistant_id == assistant_id,
                ShareScope.stage == "effective",
            )
            .limit(1)
        )
        is not None
    )


def main() -> None:
    dry_run = "--yes" not in sys.argv
    if dry_run:
        print("预演模式：只打印将修复的审批单，不写库。确认执行请追加 --yes\n")

    now: datetime = now_second()
    fixed = 0

    with SessionLocal() as db:
        approvals = db.scalars(
            select(Approval)
            .where(Approval.status == "approved")
            .order_by(Approval.id)
        ).all()

        for approval in approvals:
            if _has_effective(db, approval.assistant_id):
                continue

            source_id = approval.final_scope_id or approval.requested_scope_id
            assistant = db.get(Assistant, approval.assistant_id)
            print(
                f"审批 #{approval.id} 助理 #{approval.assistant_id}"
                f"（{assistant.name if assistant else '已删除'}）"
                f" 源范围 #{source_id}"
            )
            if source_id is None or assistant is None:
                print("  → 跳过：缺少源范围或助理已删除")
                continue

            scopes = ScopeService(db)
            payload = scopes.payload_of_snapshot(source_id)
            if payload is None:
                print("  → 跳过：源范围快照不存在")
                continue

            if dry_run:
                print("  → 将新建 effective 快照并重算授权")
                fixed += 1
                continue

            effective = scopes.create_snapshot(
                company_id=approval.company_id,
                assistant_id=approval.assistant_id,
                stage="effective",
                payload=payload,
                created_by=approval.approver_id or approval.submitter_id,
                approval_id=approval.id,
            )
            approval.final_scope_id = effective.id
            approval.updated_at = now
            total = scopes.rebuild_grants(assistant, effective.id, payload, now)
            assistant.updated_at = now
            print(f"  → 新建 effective 快照 #{effective.id}，重算授权 {total} 人")
            fixed += 1

        if dry_run:
            print(f"\n共 {fixed} 条待修复（未写库）")
            return

        db.commit()
        print(f"\n已修复 {fixed} 条审批单")


if __name__ == "__main__":
    main()
