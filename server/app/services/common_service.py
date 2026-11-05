"""通用服务：头像上传预签名（对应 docs/03 §9.1）。

本期未接入对象存储，返回本地占位地址并保留文档约定的响应结构，
前端可照常完成「预签名 → 直传 → 提交 avatarUrl」的流程改造；
接入 OSS / S3 后替换 _build_presign 即可。
"""

import hashlib
from datetime import datetime

from app.core.config import settings
from app.core.errors import BizError, ErrorCode
from app.schemas.common import AvatarPresignPayload, AvatarPresignResult

AVATAR_MAX_SIZE = 2 * 1024 * 1024
PRESIGN_EXPIRES_IN = 600
_ALLOWED_PREFIX = "image/"


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

    base = settings.avatar_base_url.rstrip("/")
    return AvatarPresignResult(
        # 占位地址：真实实现返回对象存储的预签名 PUT 地址
        upload_url=f"{base}/upload?key={object_key}&expires={PRESIGN_EXPIRES_IN}",
        object_key=object_key,
        public_url=f"{base}/{object_key}",
        expires_in=PRESIGN_EXPIRES_IN,
    )
