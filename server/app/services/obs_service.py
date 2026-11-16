"""对象存储（天翼云 OBS，S3 兼容）客户端封装。

只负责最小的读写能力：上传字节流、拼对外 URL。客户端懒加载并复用。
注意：该网关不支持 botocore 默认的 CRC32 校验与 aws-chunked 编码，
必须保持 `request_checksum_calculation="when_required"`。
"""

from __future__ import annotations

import logging
import threading
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.core.errors import BizError, ErrorCode

logger = logging.getLogger("app.obs")

_client = None
_lock = threading.Lock()


def _endpoint_url() -> str:
    """端点若带桶名（虚拟主机形式），剥掉桶名交给 boto3 自动拼接。"""
    endpoint = settings.obs_endpoint.rstrip("/")
    host = urlparse(endpoint).hostname or ""
    bucket = settings.obs_bucket
    if bucket and host.startswith(bucket + "."):
        endpoint = endpoint.replace(host, host[len(bucket) + 1 :], 1)
    return endpoint


def get_client():
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = boto3.client(
                    "s3",
                    endpoint_url=_endpoint_url(),
                    aws_access_key_id=settings.obs_ak,
                    aws_secret_access_key=settings.obs_sk,
                    region_name=settings.obs_region,
                    verify=settings.obs_ca_bundle or None,
                    config=Config(
                        signature_version="s3v4",
                        s3={"addressing_style": "virtual"},
                        request_checksum_calculation="when_required",
                        response_checksum_validation="when_required",
                        connect_timeout=8,
                        read_timeout=30,
                        retries={"max_attempts": 2},
                    ),
                )
    return _client


def upload_bytes(object_key: str, content: bytes, content_type: str) -> None:
    try:
        get_client().put_object(
            Bucket=settings.obs_bucket,
            Key=object_key,
            Body=content,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as exc:
        raise BizError(
            ErrorCode.INTERNAL_ERROR,
            "头像上传失败，请稍后重试",
            {"reason": str(exc)[:200]},
            502,
        ) from exc


def public_url(object_key: str) -> str:
    return f"{settings.obs_base_url}/{object_key.lstrip('/')}"


def delete_object(object_key: str) -> None:
    """删除对象；失败只记日志，不影响主流程。"""
    try:
        get_client().delete_object(Bucket=settings.obs_bucket, Key=object_key)
    except (BotoCoreError, ClientError) as exc:
        logger.warning("OBS 对象删除失败 key=%s error=%s", object_key, exc)
