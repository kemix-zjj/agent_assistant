"""助理版本号规则（需求 4.0 助理版本号规则）。

- 版本号格式 `V{主版本}.{次版本}.{尾号}`，空串表示「未发布」
- 首次共享审批通过记 `V1.0.0`
- 此后每次变更 / 授权范围变更 / 重新共享审批通过尾号 +1
- 尾号到 99 进位（次版本 +1、尾号归零），如 `V1.0.99` → `V1.1.0`
- 审批中、编辑保存、审批被拒、下架生效均不改变版本号
"""

import re

_VERSION_RE = re.compile(r"^V(\d+)\.(\d+)\.(\d+)$")

UNPUBLISHED = "未发布"


def next_version(version: str | None) -> str:
    """审批通过时推进版本号；无有效版本号时返回首个正式版本 V1.0.0。"""
    match = _VERSION_RE.match(version or "")
    if match is None:
        return "V1.0.0"

    major, minor, patch = (int(part) for part in match.groups())
    patch += 1
    if patch > 99:
        patch = 0
        minor += 1
    return f"V{major}.{minor}.{patch}"


def display_version(version: str | None) -> str:
    """页面展示值：空串统一展示为「未发布」。"""
    return version or UNPUBLISHED
