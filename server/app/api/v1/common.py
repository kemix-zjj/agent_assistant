"""通用接口路由（对应 docs/03 接口 29、33）。"""

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.response import ok
from app.core.security import CurrentUser, get_current_user
from app.schemas.common import AvatarPresignPayload
from app.services.common_service import build_avatar_presign, save_avatar

router = APIRouter(prefix="/common", tags=["common"])


@router.post("/avatar-presign", summary="头像上传预签名")
def avatar_presign(
    payload: AvatarPresignPayload,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    result = build_avatar_presign(payload)
    return ok(result.model_dump(by_alias=True))


@router.post("/avatar-upload", summary="头像上传（本地存储）", status_code=201)
def avatar_upload(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    content = file.file.read()
    result = save_avatar(file.filename or "avatar.png", file.content_type or "", content)
    return ok(result.model_dump(by_alias=True))
