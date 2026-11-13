"""业务单号生成：审批单号与批次号（秒级精度不足以保证唯一，取微秒）。"""

from datetime import datetime


def batch_no() -> str:
    now = datetime.now()
    return f"B{now:%Y%m%d%H%M%S}{now.microsecond:06d}"


def approval_no(seq: int = 1) -> str:
    """审批单号：AP + 时间戳（含微秒）+ 批次内序号，长度 25，适配 VARCHAR(32)。"""
    now = datetime.now()
    return f"AP{now:%Y%m%d%H%M%S}{now.microsecond:06d}{seq:02d}"
