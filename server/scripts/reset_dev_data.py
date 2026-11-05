"""一次性重置本地开发库的测试痕迹（召唤记录 + 审计 + 授权 + 审批 + 快照）。

执行前会打印将删除的行数并要求确认，避免误删演示数据。
演示数据只有 assistant（6 条）、assistant_category（5 条）及其关联的标签等，
这些表的行都挂在演示助理上，不在此清理范围内。
"""

import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import engine  # noqa: E402

# 只清「测试会新增」的表，助理与分类字典属演示数据不动
TABLES = (
    "sys_audit_log",
    "assistant_summon",
    "assistant_grant",
    "share_scope_item",
    "share_scope",
    "approval",
    "assistant_version_history",
)


def main() -> None:
    if "--yes" not in sys.argv:
        print("将清空以下表：", ", ".join(TABLES))
        print("演示数据（assistant / assistant_category 及其标签）不受影响。")
        print("确认执行请追加 --yes")
        return

    with engine.begin() as conn:
        ids = [
            row[0]
            for row in conn.execute(
                text("SELECT id FROM assistant WHERE deleted_at IS NOT NULL")
            )
        ]
        if ids:
            id_list = ", ".join(str(int(i)) for i in ids)
            conn.execute(text(f"DELETE FROM assistant WHERE id IN ({id_list})"))
            print(f"已物理删除逻辑删除的测试助理 {len(ids)} 条")

        for table in TABLES:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            conn.execute(text(f"DELETE FROM {table}"))
            print(f"{table}: 原有 {count} 行，已清理")

    with engine.connect() as conn:
        stats = conn.execute(
            text(
                "SELECT (SELECT COUNT(*) FROM assistant) a,"
                " (SELECT COUNT(*) FROM assistant_category) c,"
                " (SELECT COUNT(*) FROM assistant_tag) t,"
                " (SELECT COUNT(*) FROM approval) p,"
                " (SELECT COUNT(*) FROM share_scope) s,"
                " (SELECT COUNT(*) FROM assistant_grant) g,"
                " (SELECT COUNT(*) FROM assistant_summon) m,"
                " (SELECT COUNT(*) FROM sys_audit_log) u"
            )
        ).one()
        print(
            f"最终：助理 {stats.a}｜分类 {stats.c}｜标签 {stats.t}｜审批 {stats.p}"
            f"｜快照 {stats.s}｜授权 {stats.g}｜召唤 {stats.m}｜审计 {stats.u}"
        )


if __name__ == "__main__":
    main()
