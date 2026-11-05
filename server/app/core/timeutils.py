"""时间工具。

MySQL 的 DATETIME 列精度为秒，写入带微秒的值会被四舍五入
（11:33:11.6 → 11:33:12），与响应中 strftime 的截断结果不一致。
因此落库时间统一先截断到秒，保证响应与库内值一致。
"""

from datetime import datetime


def now_second() -> datetime:
    return datetime.now().replace(microsecond=0)


def fmt(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def fmt_required(value: datetime | None) -> str:
    return fmt(value) or ""
