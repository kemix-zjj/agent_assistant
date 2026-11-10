"""大模型调用封装（OpenAI 兼容 /chat/completions）。

配置来源：server/.env 中的 LLM_* 项（见 app/core/config.py），
默认对接 https://nisai-tools-yc.nistone.com/v1，模型 huaweicloud/deepseek-v4.1-flash-1017。
"""

import logging
import ssl

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _ssl_context() -> ssl.SSLContext:
    """使用操作系统信任库（Windows 证书存储），兼容企业内网证书链。

    certifi 自带的根证书里没有企业内网 CA，直接用它校验会报
    CERTIFICATE_VERIFY_FAILED，因此这里显式加载系统证书库。
    """
    return ssl.create_default_context()


class LlmError(Exception):
    """大模型调用失败：未配置、网络异常、超时、非 200、返回体不合法。"""


def is_enabled() -> bool:
    """未配置 API Key 或显式关闭时，由调用方回退本地模板。"""
    settings = get_settings()
    return bool(settings.llm_enabled and settings.llm_api_key)


def chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.6,
    max_tokens: int = 2000,
) -> str:
    """调用大模型并返回首条输出的文本内容。

    注意：当前模型（deepseek-v4.1-flash）是推理模型，会先消耗 reasoning_tokens
    再产出 content，max_tokens 过小会导致 content 为空、finish_reason=length，
    因此默认值给得较宽。
    """
    settings = get_settings()
    if not is_enabled():
        raise LlmError("大模型未启用或缺少 LLM_API_KEY")

    url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if settings.llm_reasoning_effort:
        payload["reasoning_effort"] = settings.llm_reasoning_effort
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    try:
        # trust_env=False：忽略系统/环境变量里的代理设置，内网模型网关需要直连
        with httpx.Client(timeout=settings.llm_timeout, trust_env=False, verify=_ssl_context()) as client:
            resp = client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise LlmError(f"大模型请求超时（{settings.llm_timeout}s）") from exc
    except httpx.HTTPError as exc:
        raise LlmError(f"大模型请求失败：{exc}") from exc

    if resp.status_code != 200:
        raise LlmError(f"大模型返回 {resp.status_code}：{resp.text[:300]}")

    try:
        body = resp.json()
        content = body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LlmError("大模型返回体不合法") from exc

    if not isinstance(content, str) or not content.strip():
        raise LlmError("大模型返回内容为空")
    return content
