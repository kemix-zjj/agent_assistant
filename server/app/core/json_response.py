"""统一 JSON 响应：在序列化前补齐 traceId。"""

from typing import Any

from fastapi.responses import JSONResponse

from app.core.logging import get_trace_id


class UnifiedJSONResponse(JSONResponse):
    """仅对统一结构 { code, message, data, traceId } 生效，其他响应原样输出。"""

    def render(self, content: Any) -> bytes:
        if (
            isinstance(content, dict)
            and "code" in content
            and "traceId" in content
            and not content["traceId"]
        ):
            content["traceId"] = get_trace_id()
        return super().render(content)
