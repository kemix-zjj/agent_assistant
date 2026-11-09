"""应用配置：从 server/.env 读取，缺省值面向本地开发。"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

# server/app/core/config.py -> server/
SERVER_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """全局配置项。字段名与 .env 中的大写键一一对应（大小写不敏感）。"""

    model_config = SettingsConfigDict(
        env_file=SERVER_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "数智助理 · 助理团"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    debug: bool = True
    log_level: str = "INFO"

    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "assistant"
    db_echo: bool = False

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # 头像对外访问域名；留空则返回后端本地 /static 相对路径
    avatar_base_url: str = ""

    @property
    def static_dir(self) -> Path:
        """本地头像落盘目录（由 main.py 挂载到 /static）。"""
        return SERVER_ROOT / "static"

    @property
    def database_url(self) -> str:
        """SQLAlchemy 连接串（MySQL 8.0 + PyMySQL 驱动）。"""
        password = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
