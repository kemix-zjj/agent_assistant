"""测试公共配置：清理测试生成的数据，避免污染开发库。

测试会产生助理、审批单、范围快照与授权记录，这里在每个测试会话开始与结束时
物理删除名称命中测试前缀的助理及其全部关联数据，保证可重复执行。
"""

import pytest
from sqlalchemy import text

from app.core.database import engine

# 测试助理名称前缀（新增测试时在此登记）
_TEST_NAME_PREFIXES = (
    "接口测试助理%",
    "共享提交助理%",
    "共享范围助理%",
    "审批测试助理%",
    "补全测试助理%",
    "端到端验证助理%",
)

# 按外键依赖倒序清理
_RELATED_TABLES = (
    "assistant_tag",
    "assistant_skill_rel",
    "assistant_mcp_rel",
    "assistant_kb_rel",
    "assistant_quick_question",
    "assistant_version_history",
    "assistant_summon",
    "assistant_grant",
)


def _purge_orphan_audit(conn) -> None:  # noqa: ANN001
    """清理指向已不存在对象的审计记录（测试物理删数据后产生）。"""
    for object_type, table in (
        ("assistant", "assistant"),
        ("approval", "approval"),
        ("grant", "assistant_grant"),
    ):
        conn.execute(
            text(
                "DELETE FROM sys_audit_log"
                f" WHERE object_type = '{object_type}'"
                "   AND NOT EXISTS ("
                f"       SELECT 1 FROM {table} t"
                "       WHERE t.id = CAST(sys_audit_log.object_id AS UNSIGNED)"
                "   )"
            )
        )


def _purge_test_summons(conn, baseline_id: int) -> None:  # noqa: ANN001
    """清理测试期间新增的召唤记录与对应审计（基线之前的不动）。

    顺序：先删审计（用 session_id 关联仍在的召唤记录），再删召唤记录。
    baseline_id 为 0 表示会话开始时表为空，此时全部记录都来自测试。
    """
    conn.execute(
        text(
            "DELETE FROM sys_audit_log"
            " WHERE action = 'assistant_summon'"
            "   AND JSON_UNQUOTE(JSON_EXTRACT(after_value, '$.sessionId')) IN ("
            "       SELECT session_id FROM assistant_summon WHERE id > :base"
            "   )"
        ),
        {"base": baseline_id},
    )
    conn.execute(text("DELETE FROM assistant_summon WHERE id > :base"), {"base": baseline_id})


def _summon_baseline(conn) -> int:  # noqa: ANN001
    return int(conn.execute(text("SELECT COALESCE(MAX(id), 0) FROM assistant_summon")).scalar() or 0)


def _purge_test_rows(summon_baseline: int = 0) -> None:
    """清掉孤儿审计记录 + 名称命中测试前缀的助理数据 + 测试新增的召唤记录。"""
    with engine.begin() as conn:
        _purge_orphan_audit(conn)
        _purge_test_summons(conn, summon_baseline)
        ids: list[int] = []
        for prefix in _TEST_NAME_PREFIXES:
            ids.extend(
                row[0]
                for row in conn.execute(
                    text("SELECT id FROM assistant WHERE name LIKE :prefix"),
                    {"prefix": prefix},
                )
            )
        ids = sorted(set(ids))
        if not ids:
            return

        id_list = ", ".join(str(int(i)) for i in ids)

        # 顺序：授权/审批引用快照 → 删审计与审批 → 删快照 → 删助理关联 → 删助理
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
        for table in _RELATED_TABLES:
            conn.execute(text(f"DELETE FROM {table} WHERE assistant_id IN ({id_list})"))

        conn.execute(
            text(
                f"DELETE FROM sys_audit_log WHERE object_type = 'assistant'"
                f" AND object_id IN ({id_list})"
            )
        )
        if approval_ids:
            approval_list = ", ".join(str(int(i)) for i in approval_ids)
            conn.execute(
                text(
                    f"DELETE FROM sys_audit_log WHERE object_type = 'approval'"
                    f" AND object_id IN ({approval_list})"
                )
            )
        conn.execute(text(f"DELETE FROM approval WHERE assistant_id IN ({id_list})"))

        if scope_ids:
            scope_list = ", ".join(str(int(i)) for i in scope_ids)
            conn.execute(text(f"DELETE FROM share_scope_item WHERE scope_id IN ({scope_list})"))
            conn.execute(text(f"DELETE FROM share_scope WHERE id IN ({scope_list})"))

        conn.execute(text(f"DELETE FROM assistant WHERE id IN ({id_list})"))


@pytest.fixture(scope="session", autouse=True)
def purge_test_assistants() -> None:
    _purge_test_rows()
    with engine.connect() as conn:
        baseline = _summon_baseline(conn)
    yield
    _purge_test_rows(baseline)
