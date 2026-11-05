"""统一响应包装与分页结构（对应 docs/03-接口设计 §2.1 / §2.2）。"""

from typing import Generic, List, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    list: List[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    pageSize: int = 12


def ok(data: object = None) -> dict:
    """成功响应体；traceId 由中间件在返回前补齐。"""
    return {"code": "OK", "message": "success", "data": data, "traceId": ""}


def fail(code: str, message: str, data: object = None) -> dict:
    return {"code": code, "message": message, "data": data, "traceId": ""}
