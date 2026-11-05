"""ORM 与数据库实表的一致性校验脚本（一次性核对用，可重复执行）。

对照 Base.metadata 中声明的表/列与 MySQL 实表，输出缺失或多余项。
"""

from pathlib import Path
import sys

from sqlalchemy import inspect

# 允许从 server/ 目录直接执行：python scripts/check_schema.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import engine  # noqa: E402
from app.models import Base  # noqa: E402

inspector = inspect(engine)
db_tables = set(inspector.get_table_names())
orm_tables = set(Base.metadata.tables)

print("仅存在于数据库：", sorted(db_tables - orm_tables - {"alembic_version"}))
print("仅存在于 ORM：", sorted(orm_tables - db_tables))

problems: list[str] = []
for table in sorted(orm_tables & db_tables):
    db_cols = {col["name"] for col in inspector.get_columns(table)}
    orm_cols = {col.name for col in Base.metadata.tables[table].columns}
    missing = orm_cols - db_cols
    # 生成列由数据库维护，ORM 不声明属正常
    extra = db_cols - orm_cols - {"active_flag", "pending_flag"}
    if missing:
        problems.append(f"{table}: ORM 多出不存在的列 {sorted(missing)}")
    if extra:
        problems.append(f"{table}: ORM 缺少列 {sorted(extra)}")

print("列差异：", problems or "无")
