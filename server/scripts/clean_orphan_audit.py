"""一次性维护：清理历史测试残留（召唤记录、孤儿审计、授权）。

生产环境不应运行；仅用于重置本地开发库到演示数据基线。
"""

import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import engine  # noqa: E402


def main() -> None:
    with engine.begin() as conn:
        orphan_audit = 0
        for object_type, table in (
            ("assistant", "assistant"),
            ("approval", "approval"),
            ("grant", "assistant_grant"),
        ):
            orphan_audit += conn.execute(
                text(
                    "DELETE FROM sys_audit_log"
                    f" WHERE object_type = '{object_type}'"
                    "   AND NOT EXISTS ("
                    f"       SELECT 1 FROM {table} t"
                    "       WHERE t.id = CAST(sys_audit_log.object_id AS UNSIGNED)"
                    "   )"
                )
            ).rowcount

        # 召唤审计与召唤记录成对清理：测试产生的会话已无对应记录
        summon_audit = conn.execute(
            text(
                "DELETE FROM sys_audit_log"
                " WHERE action = 'assistant_summon'"
                "   AND NOT EXISTS ("
                "       SELECT 1 FROM assistant_summon s"
                "       WHERE JSON_UNQUOTE("
                "           JSON_EXTRACT(sys_audit_log.after_value, '$.sessionId')"
                "       ) = s.session_id"
                "   )"
            )
        ).rowcount

        # 指向已删除助理的召唤记录
        orphan_summon = conn.execute(
            text(
                "DELETE FROM assistant_summon"
                " WHERE NOT EXISTS ("
                "       SELECT 1 FROM assistant a"
                "       WHERE a.id = assistant_summon.assistant_id"
                "   )"
            )
        ).rowcount

        print(f"孤儿审计 {orphan_audit} 条｜召唤审计 {summon_audit} 条｜孤儿召唤 {orphan_summon} 条")

    with engine.connect() as conn:
        stats = conn.execute(
            text(
                "SELECT (SELECT COUNT(*) FROM assistant) assistants,"
                " (SELECT COUNT(*) FROM approval) approvals,"
                " (SELECT COUNT(*) FROM share_scope) scopes,"
                " (SELECT COUNT(*) FROM assistant_grant) grants,"
                " (SELECT COUNT(*) FROM assistant_summon) summons,"
                " (SELECT COUNT(*) FROM sys_audit_log) audits"
            )
        ).one()
        print(
            f"助理 {stats.assistants}｜审批 {stats.approvals}｜快照 {stats.scopes}"
            f"｜授权 {stats.grants}｜召唤 {stats.summons}｜审计 {stats.audits}"
        )


if __name__ == "__main__":
    main()
