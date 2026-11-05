"""全局异常处理器：把各类异常统一翻译为 { code, message, data, traceId }。"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import BizError, ErrorCode
from app.core.logging import get_trace_id
from app.core.response import fail

logger = logging.getLogger("app.error")

# 数据库唯一键名 -> 业务错误码，避免把底层约束名暴露给前端
_UNIQUE_CONSTRAINT_MAP: dict[str, tuple[ErrorCode, str, str]] = {
    "uk_assistant_company_name": (
        ErrorCode.ASSISTANT_NAME_DUPLICATED,
        "助理昵称已存在，请修改",
        "name",
    ),
    "uk_category_company_name": (ErrorCode.CATEGORY_DUPLICATED, "分类名称已存在", "name"),
    "uk_approval_pending_assistant": (
        ErrorCode.ASSISTANT_STATUS_CHANGED,
        "该助理已有待审批申请，请刷新后重试",
        "",
    ),
}


def _body(code: str, message: str, data: object = None) -> dict:
    return {**fail(code, message, data), "traceId": get_trace_id()}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BizError)
    async def _biz_error(_: Request, exc: BizError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content=_body(exc.code.value, exc.message, exc.data),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
        return JSONResponse(
            status_code=400,
            content=_body(
                ErrorCode.PARAM_INVALID.value,
                first.get("msg", "参数不合法"),
                {"field": field} if field else None,
            ),
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        text = str(exc.orig)
        for key, (code, message, field) in _UNIQUE_CONSTRAINT_MAP.items():
            if key in text:
                return JSONResponse(
                    status_code=409,
                    content=_body(code.value, message, {"field": field}),
                )
        logger.warning("未映射的数据库约束异常：%s", text)
        return JSONResponse(
            status_code=500,
            content=_body(ErrorCode.INTERNAL_ERROR.value, "数据保存失败，请稍后重试"),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: ErrorCode.UNAUTHENTICATED,
            403: ErrorCode.NO_PERMISSION,
            404: ErrorCode.ASSISTANT_NOT_FOUND,
        }.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(code.value, str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("未处理异常：%s", exc)
        return JSONResponse(
            status_code=500,
            content=_body(ErrorCode.INTERNAL_ERROR.value, "操作失败，请稍后重试"),
        )
