"""通用服务：头像上传（对应 docs/03 §9.1）。

本期未接入对象存储，头像由后端落盘到 `server/static/avatar/...` 并挂载为 `/static`，
返回短路径作为 `avatarUrl` 提交给创建 / 编辑接口（契约中 avatarUrl 上限 512 字符）。
接入 OSS / S3 后，把 `save_avatar` 换成直传 + `public_url` 即可，响应结构不变。
"""

import hashlib
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.core.errors import BizError, ErrorCode
from app.schemas.common import (
    AvatarPresignPayload,
    AvatarPresignResult,
    AvatarUploadResult,
)

AVATAR_MAX_SIZE = 2 * 1024 * 1024
PRESIGN_EXPIRES_IN = 600
_ALLOWED_PREFIX = "image/"
_ALLOWED_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}


def build_avatar_presign(payload: AvatarPresignPayload) -> AvatarPresignResult:
    if not payload.content_type.startswith(_ALLOWED_PREFIX):
        raise BizError(
            ErrorCode.AVATAR_TYPE_INVALID,
            "仅支持 image/* 图片",
            {"field": "contentType"},
            400,
        )
    if payload.file_size > AVATAR_MAX_SIZE:
        raise BizError(
            ErrorCode.AVATAR_TOO_LARGE,
            "图片不能超过 2MB",
            {"field": "fileSize", "maxSize": AVATAR_MAX_SIZE},
            400,
        )

    now = datetime.now()
    ext = payload.file_name.rsplit(".", 1)[-1].lower() if "." in payload.file_name else "png"
    digest = hashlib.sha256(
        f"{payload.file_name}:{payload.file_size}:{now.timestamp()}".encode()
    ).hexdigest()[:16]
    object_key = f"avatar/{now:%Y/%m/%d}/{digest}.{ext}"

    return AvatarPresignResult(
        # 占位地址：真实实现返回对象存储的预签名 PUT 地址
        upload_url=f"{settings.api_prefix}/common/avatar-upload",
        object_key=object_key,
        public_url=_public_url(object_key),
        expires_in=PRESIGN_EXPIRES_IN,
    )


def save_avatar(file_name: str, content_type: str, content: bytes) -> AvatarUploadResult:
    """校验并保存上传的头像，返回可直接用作 avatarUrl 的短路径。"""
    if not content_type.startswith(_ALLOWED_PREFIX):
        raise BizError(
            ErrorCode.AVATAR_TYPE_INVALID,
            "仅支持 image/* 图片",
            {"field": "file"},
            400,
        )
    if len(content) > AVATAR_MAX_SIZE:
        raise BizError(
            ErrorCode.AVATAR_TOO_LARGE,
            "图片不能超过 2MB",
            {"field": "file", "maxSize": AVATAR_MAX_SIZE},
            400,
        )

    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if ext not in _ALLOWED_EXTS:
        ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}.get(
            content_type, "png"
        )

    now = datetime.now()
    digest = hashlib.sha256(f"{file_name}:{now.timestamp()}".encode()).hexdigest()[:16]
    object_key = f"avatar/{now:%Y/%m/%d}/{digest}.{ext}"

    target: Path = settings.static_dir / object_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)

    return AvatarUploadResult(object_key=object_key, avatar_url=_public_url(object_key))


def _public_url(object_key: str) -> str:
    base = settings.avatar_base_url.rstrip("/")
    return f"{base}/static/{object_key}" if base else f"/static/{object_key}"
