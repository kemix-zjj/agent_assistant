"""业务错误码与统一异常（对应 docs/03-接口设计 §2.4）。"""

from enum import Enum


class ErrorCode(str, Enum):
    """业务错误码（Python 3.10 无 StrEnum，用 str + Enum 等价实现）。"""

    OK = "OK"
    PARAM_INVALID = "PARAM_INVALID"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    NO_PERMISSION = "NO_PERMISSION"
    ASSISTANT_NOT_FOUND = "ASSISTANT_NOT_FOUND"
    APPROVAL_NOT_FOUND = "APPROVAL_NOT_FOUND"
    ASSISTANT_NAME_DUPLICATED = "ASSISTANT_NAME_DUPLICATED"
    ASSISTANT_NOT_OWNER = "ASSISTANT_NOT_OWNER"
    ASSISTANT_NOT_AVAILABLE = "ASSISTANT_NOT_AVAILABLE"
    ASSISTANT_STATUS_CHANGED = "ASSISTANT_STATUS_CHANGED"
    APPROVAL_ALREADY_HANDLED = "APPROVAL_ALREADY_HANDLED"
    SHARE_SCOPE_EMPTY = "SHARE_SCOPE_EMPTY"
    SHARE_SCOPE_EXCEED_LIMIT = "SHARE_SCOPE_EXCEED_LIMIT"
    SHARE_SCOPE_IMMUTABLE = "SHARE_SCOPE_IMMUTABLE"
    RESOURCE_UNAVAILABLE = "RESOURCE_UNAVAILABLE"
    KB_NO_PERMISSION = "KB_NO_PERMISSION"
    ASSISTANT_ALREADY_SHARED = "ASSISTANT_ALREADY_SHARED"
    GRANT_INVALID = "GRANT_INVALID"
    REJECT_REASON_REQUIRED = "REJECT_REASON_REQUIRED"
    REJECT_REASON_TOO_LONG = "REJECT_REASON_TOO_LONG"
    AI_GENERATE_FAILED = "AI_GENERATE_FAILED"
    CATEGORY_DUPLICATED = "CATEGORY_DUPLICATED"
    CATEGORY_NAME_TOO_LONG = "CATEGORY_NAME_TOO_LONG"
    AVATAR_TOO_LARGE = "AVATAR_TOO_LARGE"
    AVATAR_TYPE_INVALID = "AVATAR_TYPE_INVALID"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class BizError(Exception):
    """业务异常。由全局异常处理器翻译成 { code, message, data, traceId }。"""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        data: dict | None = None,
        http_status: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data
        self.http_status = http_status


class NotFoundError(BizError):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(code, message, None, 404)


class UnauthenticatedError(BizError):
    def __init__(self, message: str = "未登录或会话已过期") -> None:
        super().__init__(ErrorCode.UNAUTHENTICATED, message, None, 401)


class NoPermissionError(BizError):
    def __init__(self, message: str = "无操作权限") -> None:
        super().__init__(ErrorCode.NO_PERMISSION, message, None, 403)


class ParamInvalidError(BizError):
    def __init__(self, message: str = "参数不合法", field: str | None = None) -> None:
        super().__init__(
            ErrorCode.PARAM_INVALID,
            message,
            {"field": field} if field else None,
            400,
        )


class ConflictError(BizError):
    def __init__(self, code: ErrorCode, message: str, data: dict | None = None) -> None:
        super().__init__(code, message, data, 409)
