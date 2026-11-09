"""更新 assistant_version_history.action 的 CHECK 约束，加入下架相关动作。

用法：在 server/ 目录执行
    python scripts/migrate_version_action_offline.py
"""

from sqlalchemy import text

from app.core.database import engine

ACTIONS = (
    "create",
    "update",
    "share_submit",
    "share_approve",
    "share_reject",
    "scope_change",
    "offline_submit",
    "offline_approve",
    "offline_reject",
    "delete",
)


def main() -> None:
    allowed = ", ".join(f"'{a}'" for a in ACTIONS)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE assistant_version_history DROP CHECK ck_version_action"))
        conn.execute(
            text(
                "ALTER TABLE assistant_version_history"
                f" ADD CONSTRAINT ck_version_action CHECK (`action` IN ({allowed}))"
            )
        )
    print("ck_version_action 已更新")


if __name__ == "__main__":
    main()
