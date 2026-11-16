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

    # ---- 对象存储（天翼云 OBS，S3 兼容） ----
    # 未配置 obs_ak / obs_sk 时头像回退本地 static 目录，方便本地开发与测试
    obs_endpoint: str = "https://nistone-ai-assistant.fjoss.xstore.ctyun.cn"
    obs_bucket: str = "nistone-ai-assistant"
    obs_region: str = "us-east-1"
    obs_ak: str = ""
    obs_sk: str = ""
    # 该域名使用私有 CA，需指定根证书；留空则使用 certifi 默认证书库
    obs_ca_bundle: str = str(SERVER_ROOT / "certs" / "endpoint-root-ca.pem")
    # 对外访问域名（CDN/自定义域名），留空则用 obs_endpoint
    obs_public_base: str = ""
    # 头像对象 key 前缀
    obs_avatar_prefix: str = "test/assistant/avatar"

    # ---- 大模型（OpenAI 兼容 /chat/completions） ----
    # 未配置 llm_api_key 时自动回退到确定性模板，接线不影响本地开发
    llm_enabled: bool = True
    llm_base_url: str = "https://nisai-tools-yc.nistone.com/v1"
    llm_model: str = "huaweicloud/deepseek-v4.1-flash-1017"
    llm_api_key: str = ""
    # deepseek-v4.1-flash 为推理模型，实测单次 2-30s 波动，超时按 30s 设
    llm_timeout: float = 30.0
    # 推理强度：minimal / low / medium / high，越低响应越快
    llm_reasoning_effort: str = "minimal"

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

    @property
    def obs_enabled(self) -> bool:
        """AK/SK 齐备才走对象存储，否则回退本地磁盘。"""
        return bool(self.obs_ak and self.obs_sk)

    @property
    def obs_base_url(self) -> str:
        """头像对象的对外访问前缀。"""
        return (self.obs_public_base or self.obs_endpoint).rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
