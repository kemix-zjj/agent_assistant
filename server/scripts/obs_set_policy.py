"""为 OBS 桶设置匿名只读策略，让头像等静态资源可被浏览器直接访问。

用法（PowerShell，密钥只走环境变量）：
    $env:OBS_AK='...'; $env:OBS_SK='...'
    python scripts/obs_set_policy.py --prefix test/assistant/

注意：策略只授予 s3:GetObject，不会开放列举、写入或删除权限。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from app.core.config import settings  # noqa: E402
from app.services import obs_service  # noqa: E402


def build_policy(bucket: str, prefixes: list[str]) -> dict:
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadAssistantAssets",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": [
                    f"arn:aws:s3:::{bucket}/{prefix.strip('/')}/*" for prefix in prefixes
                ],
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="设置 OBS 桶匿名只读策略")
    parser.add_argument(
        "--prefix",
        action="append",
        default=[],
        help="允许匿名读取的前缀，可重复；默认 test/assistant/",
    )
    args = parser.parse_args()

    prefixes = args.prefix or ["test/assistant/"]
    policy = build_policy(settings.obs_bucket, prefixes)
    print(f"桶: {settings.obs_bucket}\n只读前缀: {', '.join(prefixes)}\n")

    try:
        client = obs_service.get_client()
        client.put_bucket_policy(Bucket=settings.obs_bucket, Policy=json.dumps(policy))
        print("策略已提交")
    except (BotoCoreError, ClientError) as exc:
        print(f"设置失败: {exc}", file=sys.stderr)
        print(
            "若网关不支持桶策略，可退化为对单个对象设置 public-read ACL，"
            "或改用 CDN/后端代理方案。",
            file=sys.stderr,
        )
        return 1

    try:
        current = client.get_bucket_policy(Bucket=settings.obs_bucket)
        print("当前策略:")
        print(json.dumps(json.loads(current["Policy"]), ensure_ascii=False, indent=2))
    except (BotoCoreError, ClientError, KeyError) as exc:
        print(f"策略已提交，但回读失败（不影响生效）: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
