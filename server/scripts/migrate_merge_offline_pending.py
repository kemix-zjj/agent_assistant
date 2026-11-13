"""下架审批中状态合并：assistant.share_status 移除 offline_pending。

调整口径：
- share_status 只保留一级状态 unshared / pending / approved / rejected / offline
- 下架审批中统一表示为 share_status='pending' + pending_type='offline'

执行内容：
1. 删除旧的 ck_assistant_share_status 约束
2. 将已有 offline_pending 行改为 pending，并补齐 pending_type='offline'
3. 重建不含 offline_pending 的 CHECK 约束

可重复执行。用法：在 server/ 目录执行
    python scripts/migrate_merge_offline_pending.py
"""

from sqlalchemy import text

from app.core.database import engine

CONSTRAINT = "ck_assistant_share_status"
NEW_VALUES = "'unshared', 'pending', 'approved', 'rejected', 'offline'"


def _constraint_exists(conn) -> bool:
    row = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS"
            " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'assistant'"
            "   AND CONSTRAINT_NAME = :name"
        ),
        {"name": CONSTRAINT},
    ).scalar()
    return bool(row)


def main() -> None:
    with engine.begin() as conn:
        if _constraint_exists(conn):
            conn.execute(text(f"ALTER TABLE assistant DROP CHECK {CONSTRAINT}"))
            print(f"已删除旧约束 {CONSTRAINT}")

        merged = conn.execute(
            text(
                "UPDATE assistant"
                " SET share_status = 'pending',"
                "     pending_type = CASE"
                "       WHEN pending_type IS NULL OR pending_type = '' THEN 'offline'"
                "       ELSE pending_type END"
                " WHERE share_status = 'offline_pending'"
            )
        ).rowcount
        print(f"已合并 offline_pending → pending：{merged} 行")

        conn.execute(
            text(
                f"ALTER TABLE assistant ADD CONSTRAINT {CONSTRAINT}"
                f" CHECK (share_status IN ({NEW_VALUES}))"
            )
        )
        print(f"已重建约束 {CONSTRAINT}：{NEW_VALUES}")

        # 修复历史脏数据：无待审批单却停留在「审批中 / 已拒绝」且缺少子类的行
        repaired_pending = conn.execute(
            text(
                "UPDATE assistant a SET"
                "  share_status = CASE WHEN a.has_shared = 1 THEN 'approved' ELSE 'unshared' END,"
                "  pending_type = NULL, reject_type = NULL"
                " WHERE a.share_status = 'pending' AND a.pending_type IS NULL"
                "   AND NOT EXISTS (SELECT 1 FROM approval ap"
                "                   WHERE ap.assistant_id = a.id AND ap.status = 'pending')"
            )
        ).rowcount
        print(f"已修复无待审批单的 pending 行：{repaired_pending} 行")

        repaired_rejected = conn.execute(
            text(
                "UPDATE assistant SET"
                "  share_status = CASE WHEN has_shared = 1 THEN 'approved' ELSE 'unshared' END,"
                "  pending_type = NULL, reject_type = NULL"
                " WHERE share_status = 'rejected' AND reject_type IS NULL"
            )
        ).rowcount
        print(f"已修复缺少拒绝子类的 rejected 行：{repaired_rejected} 行")

        cleared = conn.execute(
            text(
                "UPDATE assistant SET pending_type = NULL, reject_type = NULL"
                " WHERE share_status IN ('unshared', 'approved', 'offline')"
                "   AND (pending_type IS NOT NULL OR reject_type IS NOT NULL)"
            )
        ).rowcount
        print(f"已清理非审批态残留子类：{cleared} 行")

        # 跨列状态一致性：审批中必须有子类、已拒绝必须有拒绝子类、其余状态不得残留
        consistency = "ck_assistant_status_consistency"
        exists = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS"
                " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'assistant'"
                "   AND CONSTRAINT_NAME = :name"
            ),
            {"name": consistency},
        ).scalar()
        if not exists:
            conn.execute(
                text(
                    f"ALTER TABLE assistant ADD CONSTRAINT {consistency} CHECK ("
                    " (share_status = 'pending' AND pending_type IS NOT NULL AND reject_type IS NULL)"
                    " OR (share_status = 'rejected' AND reject_type IS NOT NULL AND pending_type IS NULL)"
                    " OR (share_status IN ('unshared', 'approved', 'offline')"
                    "     AND pending_type IS NULL AND reject_type IS NULL))"
                )
            )
            print(f"已新增约束 {consistency}")
        else:
            print(f"约束 {consistency} 已存在，跳过")

    print("迁移完成")


if __name__ == "__main__":
    main()
