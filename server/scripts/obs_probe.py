"""OBS 连通性探测脚本：确认 AK/SK、端点、桶是否可用，并列出桶根下的目录。

用法（PowerShell，密钥只走环境变量，不写入代码）：
    $env:OBS_AK='...'; $env:OBS_SK='...'; python scripts/obs_probe.py

可选环境变量：
    OBS_ENDPOINT  桶访问地址，默认 https://nistone-ai-assistant.fjoss.xstore.ctyun.cn
    OBS_BUCKET    桶名，默认取端点主机名的第一段
    OBS_REGION    S3 签名区域，默认 us-east-1（多数 S3 兼容端点不校验）
    OBS_PREFIX    只列某个前缀下的内容（如 avatar/）
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

DEFAULT_ENDPOINT = "https://nistone-ai-assistant.fjoss.xstore.ctyun.cn"


@dataclass(frozen=True)
class Attempt:
    endpoint: str
    style: str
    signature: str
    region: str

    def describe(self) -> str:
        return f"endpoint={self.endpoint} style={self.style} sig={self.signature} region={self.region}"


def _build_client(
    attempt: Attempt, ak: str, sk: str, insecure: bool = False, ca_bundle: str | None = None
):
    return boto3.client(
        "s3",
        endpoint_url=attempt.endpoint,
        aws_access_key_id=ak,
        aws_secret_access_key=sk,
        region_name=attempt.region,
        verify=False if insecure else (ca_bundle or None),
        config=Config(
            signature_version=attempt.signature,
            s3={"addressing_style": attempt.style},
            connect_timeout=8,
            read_timeout=20,
            retries={"max_attempts": 0},
        ),
    )


def _attempts(endpoint: str, bucket: str, region: str) -> list[Attempt]:
    """依次尝试 虚拟主机/路径 两种寻址方式与 v4/v2 两种签名。"""
    parsed = urlparse(endpoint)
    host = parsed.hostname or ""
    base_endpoint = endpoint
    if host.startswith(bucket + "."):
        base_endpoint = endpoint.replace(host, host[len(bucket) + 1 :], 1)

    pairs = [
        (base_endpoint, "virtual"),
        (base_endpoint, "path"),
        (endpoint, "path"),
        (endpoint, "virtual"),
    ]
    result: list[Attempt] = []
    for signature in ("s3v4", "s3"):
        for ep, style in pairs:
            result.append(Attempt(ep, style, signature, region))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="OBS 桶目录探测")
    parser.add_argument("--endpoint", default=os.getenv("OBS_ENDPOINT", DEFAULT_ENDPOINT))
    parser.add_argument("--bucket", default=os.getenv("OBS_BUCKET", ""))
    parser.add_argument("--ak", default=os.getenv("OBS_AK", ""))
    parser.add_argument("--sk", default=os.getenv("OBS_SK", ""))
    parser.add_argument("--region", default=os.getenv("OBS_REGION", "us-east-1"))
    parser.add_argument("--prefix", default=os.getenv("OBS_PREFIX", ""))
    parser.add_argument("--insecure", action="store_true", help="跳过 TLS 证书校验（仅排障用）")
    parser.add_argument("--ca-bundle", default=os.getenv("OBS_CA_BUNDLE", ""), help="自定义 CA 证书 PEM 路径")
    args = parser.parse_args()

    if args.insecure:
        import urllib3

        urllib3.disable_warnings()
        print("警告：已跳过 TLS 证书校验，仅用于排障。\n")

    bucket = args.bucket or (urlparse(args.endpoint).hostname or "").split(".")[0]
    if not (args.ak and args.sk):
        print("缺少 AK/SK：请通过 OBS_AK / OBS_SK 环境变量或 --ak/--sk 传入", file=sys.stderr)
        return 2

    print(f"桶: {bucket}\n端点: {args.endpoint}\n")

    client = None
    last_error: Exception | None = None
    for attempt in _attempts(args.endpoint, bucket, args.region):
        try:
            candidate = _build_client(
                attempt, args.ak, args.sk, args.insecure, args.ca_bundle or None
            )
            candidate.list_objects_v2(Bucket=bucket, Delimiter="/", MaxKeys=1)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            message = exc.response.get("Error", {}).get("Message", str(exc))
            print(f"[失败] {attempt.describe()} -> {code}: {message}")
            last_error = exc
            continue
        except (BotoCoreError, Exception) as exc:  # noqa: BLE001 网络/SSL/签名配置错误
            print(f"[失败] {attempt.describe()} -> {type(exc).__name__}: {exc}")
            last_error = exc
            continue

        print(f"[成功] {attempt.describe()}\n")
        client = candidate
        break

    if client is None:
        print("\n所有组合均失败，请确认端点是否兼容 S3 协议、AK/SK 是否有效。", file=sys.stderr)
        if last_error:
            print(f"最后一个错误: {last_error}", file=sys.stderr)
        return 1

    # 列出根目录下的“目录”（以 / 结尾的公共前缀）与根级对象
    try:
        resp = client.list_objects_v2(
            Bucket=bucket, Delimiter="/", MaxKeys=1000, Prefix=args.prefix
        )
    except ClientError as exc:
        print(f"列出对象失败: {exc}", file=sys.stderr)
        return 1

    prefixes = [item["Prefix"] for item in resp.get("CommonPrefixes", [])]
    objects = [item["Key"] for item in resp.get("Contents", [])]

    print(f"目录（{len(prefixes)} 个）:")
    for prefix in prefixes:
        print(f"  - {prefix}")
    if not prefixes:
        print("  （无）")

    print(f"\n根级对象（{len(objects)} 个，最多展示 20 个）:")
    for key in objects[:20]:
        print(f"  - {key}")
    if not objects:
        print("  （无）")
    if resp.get("IsTruncated"):
        print("\n提示：结果被截断（超过 1000 项），可用 --prefix 缩小范围。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
