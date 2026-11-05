"""清理开发库中的验证用途数据（可重复执行）。

删除名称命中测试前缀的助理及其关联数据；这些记录由测试与验证脚本产生，
不属于演示数据。
"""

import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import engine  # noqa: E402

PREFIXES = (
    "接口测试助理%",
    "共享提交助理%",
    "共享范围助理%",
    "审批测试助理%",
    "端到端验证助理%",
)

RELATED_TABLES = (
    "assistant_tag",
    "assistant_skill_rel",
    "assistant_mcp_rel",
    "assistant_kb_rel",
    "assistant_quick_question",
    "assistant_version_history",
    "assistant_summon",
    "assistant_grant",
)


def main() -> None:
    with engine.begin() as conn:
        ids: list[int] = []
        for prefix in PREFIXES:
            ids.extend(
                row[0]
                for row in conn.execute(
                    text("SELECT id FROM assistant WHERE name LIKE :p"), {"p": prefix}
                )
            )
        ids = sorted(set(ids))

        if ids:
            id_list = ", ".join(str(int(i)) for i in ids)
            scope_ids = [
                row[0]
                for row in conn.execute(
                    text(f"SELECT id FROM share_scope WHERE assistant_id IN ({id_list})")
                )
            ]
            approval_ids = [
                row[0]
                for row in conn.execute(
                    text(f"SELECT id FROM approval WHERE assistant_id IN ({id_list})")
                )
            ]
            for table in RELATED_TABLES:
                conn.execute(text(f"DELETE FROM {table} WHERE assistant_id IN ({id_list})"))

            conn.execute(
                text(
                    "DELETE FROM sys_audit_log WHERE object_type = 'assistant'"
                    f" AND object_id IN ({id_list})"
                )
            )
            if approval_ids:
                approval_list = ", ".join(str(int(i)) for i in approval_ids)
                conn.execute(
                    text(
                        "DELETE FROM sys_audit_log WHERE object_type = 'approval'"
                        f" AND object_id IN ({approval_list})"
                    )
                )
            conn.execute(text(f"DELETE FROM approval WHERE assistant_id IN ({id_list})"))

            if scope_ids:
                scope_list = ", ".join(str(int(i)) for i in scope_ids)
                conn.execute(
                    text(f"DELETE FROM share_scope_item WHERE scope_id IN ({scope_list})")
                )
                conn.execute(text(f"DELETE FROM share_scope WHERE id IN ({scope_list})"))
            conn.execute(text(f"DELETE FROM assistant WHERE id IN ({id_list})"))
            print(f"已清理 {len(ids)} 条测试助理及其审批/范围/授权/审计数据：{ids}")
        else:
            print("无需清理：开发库中没有测试助理。")

    with engine.connect() as conn:
        stats = conn.execute(
            text(
                "SELECT (SELECT COUNT(*) FROM assistant) assistants,"
                " (SELECT COUNT(*) FROM assistant WHERE deleted_at IS NULL) alive,"
                " (SELECT COUNT(*) FROM approval) approvals,"
                " (SELECT COUNT(*) FROM share_scope) scopes,"
                " (SELECT COUNT(*) FROM assistant_grant) grants,"
                " (SELECT COUNT(*) FROM sys_audit_log) audits"
            )
        ).one()
        print(
            f"助理 {stats.assistants}（未删除 {stats.alive}）｜审批单 {stats.approvals}"
            f"｜范围快照 {stats.scopes}｜授权 {stats.grants}｜审计 {stats.audits}"
        )


if __name__ == "__main__":
    main()
