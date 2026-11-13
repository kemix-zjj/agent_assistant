"""存量库升级：对齐 V1.0.0 版本号口径与审批子类字段。

需求变更点（原型 2026-11 版）：
1. `assistant` 新增 `pending_type` / `reject_type` / `has_shared` / `offline_reason`
2. `assistant.version` 由 `v1.0` 两段式改为 `V1.0.0` 三段式，空串表示「未发布」
3. `approval.approval_type` 的 `scope_change` 重命名为 `scope`，并新增 `change` 调整申请
4. `assistant_version_history.action` 新增 `change_submit` / `change_approve` /
   `change_reject` / `scope_reject`

可重复执行（逐条判断后再变更）。用法：在 server/ 目录执行
    python scripts/migrate_v100_schema.py
"""

from sqlalchemy import inspect, text

from app.core.database import engine

ASSISTANT_COLUMNS = {
    "pending_type": "VARCHAR(16) NULL COMMENT '审批子类：share / change / scope / offline'",
    "reject_type": "VARCHAR(16) NULL COMMENT '拒绝子类：share / change / scope / offline'",
    "has_shared": "TINYINT NOT NULL DEFAULT 0 COMMENT '是否曾共享成功过'",
    "offline_reason": "VARCHAR(200) NULL COMMENT '下架原因'",
}

VERSION_ACTIONS = (
    "create",
    "update",
    "share_submit",
    "share_approve",
    "share_reject",
    "change_submit",
    "change_approve",
    "change_reject",
    "scope_change",
    "scope_reject",
    "offline_submit",
    "offline_approve",
    "offline_reject",
    "delete",
)


def _columns(conn, table: str) -> set[str]:
    return {col["name"] for col in inspect(conn).get_columns(table)}


def _constraint_exists(conn, table: str, name: str) -> bool:
    row = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS"
            " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table"
            "   AND CONSTRAINT_NAME = :name"
        ),
        {"table": table, "name": name},
    ).scalar()
    return bool(row)


def _index_exists(conn, table: str, name: str) -> bool:
    row = conn.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.STATISTICS"
            " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table"
            "   AND INDEX_NAME = :name"
        ),
        {"table": table, "name": name},
    ).scalar()
    return bool(row)


def main() -> None:
    with engine.begin() as conn:
        # 1. assistant 补列
        existing = _columns(conn, "assistant")
        for name, ddl in ASSISTANT_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE assistant ADD COLUMN `{name}` {ddl}"))
                print(f"assistant 新增列 {name}")

        # 2. 版本号格式 v1.2 -> V1.2.0
        conn.execute(
            text(
                "UPDATE assistant SET version = CONCAT('V', SUBSTRING(version, 2), '.0')"
                " WHERE version REGEXP '^v[0-9]+\\\\.[0-9]+$'"
            )
        )
        # 未共享状态的助理不应有版本号，统一置空（页面展示「未发布」）
        conn.execute(
            text("UPDATE assistant SET version = '' WHERE share_status = 'unshared'")
        )
        # 已共享成功的助理标记 has_shared
        conn.execute(
            text(
                "UPDATE assistant SET has_shared = 1"
                " WHERE share_status IN ('approved', 'offline_pending', 'offline')"
            )
        )

        # 3. 审批类型口径：先放宽约束再改值，避免旧 CHECK 拦截 scope_change -> scope
        if _constraint_exists(conn, "approval", "ck_approval_type"):
            conn.execute(text("ALTER TABLE approval DROP CHECK ck_approval_type"))
        conn.execute(
            text("UPDATE approval SET approval_type = 'scope' WHERE approval_type = 'scope_change'")
        )
        conn.execute(
            text(
                "ALTER TABLE approval ADD CONSTRAINT ck_approval_type"
                " CHECK (approval_type IN ('share', 'scope', 'change', 'offline'))"
            )
        )

        # 4. 版本记录 action 约束扩展
        if _constraint_exists(conn, "assistant_version_history", "ck_version_action"):
            conn.execute(
                text("ALTER TABLE assistant_version_history DROP CHECK ck_version_action")
            )
        allowed = ", ".join(f"'{a}'" for a in VERSION_ACTIONS)
        conn.execute(
            text(
                "ALTER TABLE assistant_version_history ADD CONSTRAINT ck_version_action"
                f" CHECK (`action` IN ({allowed}))"
            )
        )
        conn.execute(
            text(
                "UPDATE assistant_version_history SET version = '未发布' WHERE version = ''"
            )
        )

        # 5. 审批子类 / 拒绝子类回填（按在途与最近被拒审批单派生）
        conn.execute(
            text(
                "UPDATE assistant a JOIN ("
                "  SELECT assistant_id, approval_type FROM approval"
                "  WHERE status = 'pending' AND id IN ("
                "    SELECT MAX(id) FROM approval WHERE status = 'pending' GROUP BY assistant_id"
                "  )"
                ") p ON p.assistant_id = a.id"
                " SET a.pending_type = p.approval_type"
                " WHERE a.share_status IN ('pending', 'offline_pending')"
            )
        )
        conn.execute(
            text(
                "UPDATE assistant a JOIN ("
                "  SELECT assistant_id, approval_type FROM approval"
                "  WHERE status = 'rejected' AND id IN ("
                "    SELECT MAX(id) FROM approval WHERE status = 'rejected' GROUP BY assistant_id"
                "  )"
                ") r ON r.assistant_id = a.id"
                " SET a.reject_type = r.approval_type"
                " WHERE a.share_status = 'rejected'"
            )
        )

    print("存量库已升级到 V1.0.0 版本号口径")


if __name__ == "__main__":
    main()
