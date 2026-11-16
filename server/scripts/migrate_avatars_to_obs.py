"""把数据库里 /static/ 开头的历史头像迁移到 OBS，并回写 assistant.avatar_url。

用法（PowerShell，密钥走环境变量或 server/.env）：
    python scripts/migrate_avatars_to_obs.py --dry-run
    python scripts/migrate_avatars_to_obs.py

对象 key 规则：{OBS_AVATAR_PREFIX}/legacy/{原 static 相对路径去掉 avatar/}
本地文件保留不删，迁移失败可直接重跑（同 key 覆盖）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from app.core.config import settings  # noqa: E402
from app.core.database import engine  # noqa: E402
from app.services import obs_service  # noqa: E402

_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def migrate(dry_run: bool) -> int:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "select id, name, avatar_url from assistant "
                "where deleted_at is null and avatar_url like '/static/%'"
            )
        ).fetchall()

        if not rows:
            print("没有需要迁移的头像")
            return 0

        migrated = 0
        for assistant_id, name, url in rows:
            rel = url[len("/static/") :]
            rel_key = rel[len("avatar/") :] if rel.startswith("avatar/") else rel
            key = f"{settings.obs_avatar_prefix.strip('/')}/legacy/{rel_key}"
            source = settings.static_dir / rel

            if not source.is_file():
                print(f"跳过 id={assistant_id} {name}: 本地文件不存在 {source}")
                continue

            new_url = obs_service.public_url(key)
            print(f"id={assistant_id} {name}\n  {url}\n  -> {new_url}")
            if dry_run:
                continue

            obs_service.upload_bytes(key, source.read_bytes(), _MIME.get(source.suffix.lower(), "image/png"))
            conn.execute(
                text("update assistant set avatar_url = :url where id = :id"),
                {"url": new_url, "id": assistant_id},
            )
            migrated += 1

        if dry_run:
            print(f"\n[dry-run] 待迁移 {len(rows)} 条")
        else:
            print(f"\n迁移完成 {migrated} 条")
        return migrated


def main() -> int:
    parser = argparse.ArgumentParser(description="迁移历史本地头像到 OBS")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不写 OBS/数据库")
    args = parser.parse_args()

    if not settings.obs_enabled:
        print("未配置 OBS_AK/OBS_SK，无法迁移", file=sys.stderr)
        return 1

    migrate(args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
