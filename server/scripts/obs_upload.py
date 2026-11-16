"""把本地图片批量上传到 OBS，按相对路径镜像到目标前缀下。

用法（PowerShell，密钥只走环境变量）：
    $env:OBS_AK='...'; $env:OBS_SK='...'
    python scripts/obs_upload.py --source web/public/avatars --prefix test/assistant/

默认上传目录为项目根，key 形如 test/assistant/web/public/avatars/avatar-01.png。
"""

from __future__ import annotations

import argparse
import mimetypes
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

SERVER_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SERVER_ROOT.parent
DEFAULT_ENDPOINT = "https://nistone-ai-assistant.fjoss.xstore.ctyun.cn"
DEFAULT_CA = SERVER_ROOT / "certs" / "endpoint-root-ca.pem"
DEFAULT_EXTS = "png,jpg,jpeg,gif,webp,svg"
SKIP_DIRS = {".git", "node_modules", "dist", "__pycache__", ".venv", ".pytest_cache"}


def _client(endpoint: str, bucket: str, ak: str, sk: str, ca_bundle: Path | None):
    host = urlparse(endpoint).hostname or ""
    if host.startswith(bucket + "."):
        endpoint = endpoint.replace(host, host[len(bucket) + 1 :], 1)
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
        region_name="us-east-1",
        verify=str(ca_bundle) if ca_bundle and ca_bundle.exists() else None,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
            # 新版 botocore 默认加 CRC32 校验与 aws-chunked 编码，部分 S3 兼容网关不支持
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
            connect_timeout=8,
            read_timeout=60,
            retries={"max_attempts": 2},
        ),
    )


def _iter_files(base: Path, exts: set[str]):
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower().lstrip(".") in exts:
            yield path


def main() -> int:
    parser = argparse.ArgumentParser(description="批量上传图片到 OBS")
    parser.add_argument("--source", action="append", default=[], help="相对项目根的目录或文件，可重复")
    parser.add_argument("--prefix", default="test/assistant/", help="目标前缀，默认 test/assistant/")
    parser.add_argument("--endpoint", default=os.getenv("OBS_ENDPOINT", DEFAULT_ENDPOINT))
    parser.add_argument("--bucket", default=os.getenv("OBS_BUCKET", ""))
    parser.add_argument("--ak", default=os.getenv("OBS_AK", ""))
    parser.add_argument("--sk", default=os.getenv("OBS_SK", ""))
    parser.add_argument("--ca-bundle", default=os.getenv("OBS_CA_BUNDLE", ""))
    parser.add_argument("--exts", default=DEFAULT_EXTS, help="逗号分隔的扩展名")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    bucket = args.bucket or (urlparse(args.endpoint).hostname or "").split(".")[0]
    if not (args.ak and args.sk):
        print("缺少 AK/SK：请通过 OBS_AK / OBS_SK 环境变量或 --ak/--sk 传入", file=sys.stderr)
        return 2

    prefix = args.prefix.strip("/") + "/" if args.prefix.strip("/") else ""
    exts = {item.strip().lower().lstrip(".") for item in args.exts.split(",") if item.strip()}

    local_files: list[Path] = []
    for source in args.source or ["."]:
        target = (PROJECT_ROOT / source).resolve()
        if not target.exists():
            print(f"跳过不存在的路径: {target}", file=sys.stderr)
            continue
        if target.is_file():
            if target.suffix.lower().lstrip(".") in exts:
                local_files.append(target)
        else:
            base = target
            for path in _iter_files(base, exts):
                local_files.append(path)

    if not local_files:
        print("没有找到待上传的图片", file=sys.stderr)
        return 1

    # 统一换算成相对项目根的 key
    def make_key(path: Path) -> str:
        try:
            rel = path.resolve().relative_to(PROJECT_ROOT)
        except ValueError:
            rel = Path(path.name)
        return prefix + rel.as_posix()

    print(f"桶: {bucket}\n目标前缀: {prefix}\n待上传: {len(local_files)} 个文件\n")
    if args.dry_run:
        for path in local_files:
            print(f"[dry-run] {path} -> {make_key(path)}")
        return 0

    ca_bundle = Path(args.ca_bundle) if args.ca_bundle else DEFAULT_CA
    try:
        client = _client(args.endpoint, bucket, args.ak, args.sk, ca_bundle)
    except (BotoCoreError, ClientError) as exc:
        print(f"创建客户端失败: {exc}", file=sys.stderr)
        return 1

    failed = 0
    for index, path in enumerate(local_files, 1):
        key = make_key(path)
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        try:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=path.read_bytes(),
                ContentType=content_type,
            )
            print(f"[{index}/{len(local_files)}] OK  {key}")
        except (BotoCoreError, ClientError) as exc:
            failed += 1
            print(f"[{index}/{len(local_files)}] 失败 {key} -> {exc}", file=sys.stderr)

    # 上传后核对目标前缀下的对象数量
    try:
        resp = client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1000)
        count = resp.get("KeyCount", 0)
        print(f"\n核对: {prefix} 下现有 {count} 个对象")
    except (BotoCoreError, ClientError) as exc:
        print(f"核对失败: {exc}", file=sys.stderr)

    print(f"完成: 成功 {len(local_files) - failed}，失败 {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
