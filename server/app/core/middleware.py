"""中间件：链路 ID 注入与访问日志。"""

import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logging import new_trace_id, set_client_ip, set_trace_id

logger = logging.getLogger("app.access")


def _client_ip(request: Request) -> str | None:
    """取真实客户端 IP：优先反向代理头，其次直连地址。"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip() or None
    return request.client.host if request.client else None


class TraceMiddleware(BaseHTTPMiddleware):
    """为每个请求生成 traceId 并写入日志；请求头带 X-Trace-Id 时复用。"""

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001, ANN201
        trace_id = request.headers.get("X-Trace-Id") or new_trace_id()
        set_trace_id(trace_id)
        set_client_ip(_client_ip(request))

        started = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000

        response.headers["X-Trace-Id"] = trace_id
        logger.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
