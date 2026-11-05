"""登录态解析：本期从网关注入的请求头读取。

正式环境由网关校验 Cookie / Authorization 后下发 X-User-Id 等头，
因此服务内部只做解析，不做登录校验。
"""

from dataclasses import dataclass
from urllib.parse import unquote

from fastapi import Header

from app.core.errors import UnauthenticatedError


@dataclass(frozen=True)
class CurrentUser:
    user_id: int
    company_id: int
    is_admin: bool
    name: str
    dept_name: str | None = None

    def require_admin(self) -> None:
        from app.core.errors import NoPermissionError

        if not self.is_admin:
            raise NoPermissionError("仅公司管理员可执行该操作")


# 开发期用固定的管理员 ID 集合标记管理员身份，接入权限中心后由网关下发 is_admin
_ADMIN_USER_IDS = {9001}


def get_current_user(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_company_id: str | None = Header(default=None, alias="X-Company-Id"),
    x_user_name: str | None = Header(default=None, alias="X-User-Name"),
    x_user_dept: str | None = Header(default=None, alias="X-User-Dept"),
) -> CurrentUser:
    if not x_user_id:
        raise UnauthenticatedError()
    try:
        user_id = int(x_user_id)
        company_id = int(x_company_id) if x_company_id else 1
    except ValueError as exc:
        raise UnauthenticatedError("登录态信息格式错误") from exc

    return CurrentUser(
        user_id=user_id,
        company_id=company_id,
        is_admin=user_id in _ADMIN_USER_IDS,
        # owner_name / operator_name 为落库快照，网关接好后由登录态直接下发。
        # HTTP 头只允许 ASCII，中文姓名按 UTF-8 百分号编码传入，此处解码。
        name=unquote(x_user_name) if x_user_name else f"用户{user_id}",
        dept_name=unquote(x_user_dept) if x_user_dept else None,
    )
