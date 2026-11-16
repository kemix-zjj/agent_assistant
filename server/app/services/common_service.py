"""通用服务：头像上传（对应 docs/03 §9.1）。

头像统一走后端中转：校验 → 生成对象 key → 写入 OBS → 返回可访问 URL。
未配置 OBS AK/SK 时回退本地 `server/static`，方便本地开发与测试。
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
from app.services import obs_service

AVATAR_MAX_SIZE = 2 * 1024 * 1024
PRESIGN_EXPIRES_IN = 600
_ALLOWED_PREFIX = "image/"
_ALLOWED_EXTS = {"png", "jpg", "jpeg", "gif", "webp"}
_MIME_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


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

    ext = payload.file_name.rsplit(".", 1)[-1].lower() if "." in payload.file_name else "png"
    digest = hashlib.sha256(
        f"{payload.file_name}:{payload.file_size}:{datetime.now().timestamp()}".encode()
    ).hexdigest()[:16]
    object_key = _object_key(ext, digest)

    return AvatarPresignResult(
        # 本期走服务端中转，预签名地址仍指向上传接口
        upload_url=f"{settings.api_prefix}/common/avatar-upload",
        object_key=object_key,
        public_url=_public_url(object_key),
        expires_in=PRESIGN_EXPIRES_IN,
    )


def save_avatar(file_name: str, content_type: str, content: bytes) -> AvatarUploadResult:
    """校验并保存上传的头像，返回可直接用作 avatarUrl 的地址。"""
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
        ext = _MIME_EXT.get(content_type, "png")

    digest = hashlib.sha256(f"{file_name}:{datetime.now().timestamp()}".encode()).hexdigest()[:16]
    object_key = _object_key(ext, digest)

    if settings.obs_enabled:
        obs_service.upload_bytes(object_key, content, content_type)
    else:
        target: Path = settings.static_dir / object_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    return AvatarUploadResult(object_key=object_key, avatar_url=_public_url(object_key))


def avatar_url_for(value: str | None) -> str | None:
    """把库里存的对象 key 拼成可访问地址；历史 URL 与本地路径原样返回。"""
    if not value or value.startswith(("http://", "https://", "/")):
        return value
    return _public_url(value)


def normalize_avatar_value(value: str | None) -> str | None:
    """把前端提交的 OBS 完整地址统一成库里存储的对象 key。"""
    if not value:
        return value
    obs_base = f"{settings.obs_base_url}/"
    return value[len(obs_base) :] if value.startswith(obs_base) else value


def delete_avatar(value: str | None) -> None:
    """删除不再引用的头像对象；预置头像与外部地址直接忽略。"""
    if not value:
        return
    prefix = settings.obs_avatar_prefix.strip("/") + "/"

    obs_base = f"{settings.obs_base_url}/"
    if value.startswith(obs_base):
        value = value[len(obs_base) :]
    elif value.startswith("/static/"):
        key = value[len("/static/") :]
        if key.startswith(prefix) or key.startswith("avatar/"):
            (settings.static_dir / key).unlink(missing_ok=True)
        return

    if value.startswith(prefix) and settings.obs_enabled:
        obs_service.delete_object(value)


def _object_key(ext: str, digest: str) -> str:
    now = datetime.now()
    prefix = settings.obs_avatar_prefix.strip("/")
    return f"{prefix}/{now:%Y/%m/%d}/{digest}.{ext}"


def _public_url(object_key: str) -> str:
    if settings.obs_enabled:
        return obs_service.public_url(object_key)
    base = settings.avatar_base_url.rstrip("/")
    return f"{base}/static/{object_key}" if base else f"/static/{object_key}"
