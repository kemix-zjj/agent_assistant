"""AI 生成服务（对应 docs/03 §8.1、需求 4.1.1.0）。

优先调用大模型（app/services/llm_client.py，OpenAI 兼容接口）：
- 大模型返回结果一律做本地二次校验与裁剪（长度、数量、去重、单标签字数），
  保证满足各字段既有规则；
- 大模型未启用（LLM_ENABLED=false 或未配置 LLM_API_KEY）时使用确定性模板，
  便于离线开发与单元测试；
- 大模型调用失败时抛出 AI_GENERATE_FAILED（502），前端保留用户原内容，
  不用模板内容覆盖用户输入。

各字段的关联输入严格对齐需求 4.1.1.0：
| 字段           | 生成（为空）              | 润色（已有内容）            |
| -------------- | ------------------------- | --------------------------- |
| description    | 名称 + 分类               | 已有描述 + 名称 + 分类      |
| tags           | 名称 + 分类 + 描述        | 已有标签补足至 5 个         |
| prompt         | 名称 + 描述 + 分类 + 标签 | 已有提示词 + 名称 + 描述    |
| quickQuestions | 名称 + 描述               | 已有问题补足至 6 条         |
"""

import json
import logging
import re

from app.core.errors import BizError, ErrorCode
from app.schemas.common import AiGeneratePayload, AiGenerateResult
from app.services import llm_client

logger = logging.getLogger(__name__)

TAG_LIMIT = 5
QUICK_QUESTION_LIMIT = 6
DESC_MIN, DESC_MAX = 10, 200
TAG_MIN_LEN, TAG_MAX_LEN = 1, 8
QUESTION_MAX_LEN = 30
PROMPT_MAX = 4000

# 标签不足 5 个时用于补齐的通用标签
TAG_FALLBACKS = ("业务问答", "制度检索", "流程指引", "数据分析", "风险提示")

# 拆词分隔符（分句）
_SEPARATORS = "，。、；：（）()【】《》「」·…— \n\t\r/-~!！?？,.;:"
# 长句内部优先按这些连接词再切一刀，提高短词召回
_INNER_SPLITTERS = (
    "结合",
    "通过",
    "支持",
    "负责",
    "输出",
    "提供",
    "包括",
    "用于",
    "面向",
    "与",
    "和",
    "及",
    "并",
    "或",
)
# 助理名称里可剥离的后缀，避免整条名称被当成标签
_NAME_SUFFIXES = ("小助理", "助理", "助手", "智能体", "智能")
# 关键词开头的动词，剥掉后更像名词标签
_VERB_PREFIXES = (
    "解答",
    "回答",
    "负责",
    "支持",
    "提供",
    "输出",
    "用于",
    "面向",
    "通过",
    "包括",
    "帮助",
    "协助",
    "针对",
    "结合",
)

# ============================ 大模型提示词 ============================

_SYSTEM_PROMPT = (
    "你是企业「数智助理」配置平台的内容助手，负责为业务人员编写的助理配置生成规范文本。"
    "输出必须是可直接使用的中文内容，不要解释你的思路，不要输出多余前后缀。"
)

_FIELD_PROMPTS = {
    "description": (
        "请为下面这位助理写一段「助理描述」，用于列表卡片展示。\n"
        "要求：\n"
        "1. 长度 {desc_min}-{desc_max} 个中文字符，一段话，不要换行、不要分点；\n"
        "2. 说明该助理面向什么场景、能解决什么问题、回答遵循什么原则；\n"
        "3. 只输出描述正文。"
    ),
    "prompt": (
        "请为下面这位助理写一段「提示词」（system prompt），用于配置大模型角色。\n"
        "要求：\n"
        "1. 以「你是……」开头，写明角色、服务范围与擅长方向；\n"
        "2. 给出 3-5 条回答要求，包含：先给结论再给依据、涉及员工个人数据须提示自行核对、"
        "无法确认时说明「需人工确认」且不得编造条款编号、需要走流程时指引审批入口；\n"
        "3. 总长度不超过 {prompt_max} 字符，使用编号列表换行排版；\n"
        "4. 只输出提示词正文。"
    ),
    "tags": (
        "请为下面这位助理生成「自定义标签」。\n"
        "要求：\n"
        "1. 共 {tag_limit} 个，互不重复；\n"
        "2. 每个标签 {tag_min}-{tag_max} 个中文字符，是名词或名词短语，不要动词开头、不要标点；\n"
        "3. 覆盖业务领域、主要能力、典型场景；\n"
        "4. 只输出 JSON 字符串数组，例如 [\"考勤规则\", \"补卡流程\"]，不要任何解释。"
    ),
    "quickQuestions": (
        "请为下面这位助理生成「召唤快速问题」，即用户召唤该助理时可直接点击的示例问题。\n"
        "要求：\n"
        "1. 共 {question_limit} 条，互不重复；\n"
        "2. 每条不超过 {question_max} 个中文字符，是用户会真实提出的问句，以问号结尾；\n"
        "3. 覆盖能力咨询、办理流程、制度依据、异常处理等角度；\n"
        "4. 只输出 JSON 字符串数组，例如 [\"考勤规则怎么规定？\"]，不要任何解释。"
    ),
}


def _fallback_name(name: str) -> str:
    return name.strip() or "业务助理"


def _category(payload: AiGeneratePayload) -> str:
    return (payload.category_name or "本部门").strip() or "本部门"


def _text(value: str | list[str] | None) -> str:
    return value.strip() if isinstance(value, str) else ""


def _items(value: str | list[str] | None) -> list[str]:
    if isinstance(value, list):
        return [item.strip() for item in value if item.strip()]
    return []


# ============================ 大模型出入参处理 ============================


def _fact_block(payload: AiGeneratePayload, mode: str) -> str:
    """把表单已知信息整理成事实清单，作为大模型输入。"""
    name = _fallback_name(payload.name)
    category = _category(payload)
    description = (payload.description or "").strip()
    tags = [tag.strip() for tag in payload.tags if tag.strip()][:TAG_LIMIT]
    current = _text(payload.current_value)
    existing = _items(payload.current_value)

    lines = [f"助理名称：{name}", f"所属分类：{category}"]
    if description:
        lines.append(f"当前描述：{description}")
    if tags:
        lines.append(f"当前标签：{'、'.join(tags)}")
    if mode == "polish":
        if payload.field in ("description", "prompt") and current:
            lines.append(f"已有内容（需在此基础上润色，保留原意）：{current}")
        elif existing:
            lines.append(f"已有条目（需在此基础上补充，不要重复这些）：{'、'.join(existing)}")
    return "\n".join(lines)


def _strip_code_fence(text: str) -> str:
    """去掉模型偶尔包裹的 ```json ... ``` 围栏。"""
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.S)
    return (fenced.group(1) if fenced else text).strip()


def _parse_string_list(raw: str) -> list[str]:
    """从模型输出里解析字符串数组；失败时退化为按行/顿号切分。"""
    text = _strip_code_fence(raw)
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [str(item).strip() for item in data if str(item).strip()]
    except (ValueError, TypeError):
        pass
    # 兜底：去掉引号与列表符号后按常见分隔符切
    cleaned = re.sub(r'[\[\]"\']', "", text)
    parts = re.split(r"[,\n、，;；]+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _clean_string_list(
    raw: list[str],
    *,
    existing: list[str],
    limit: int,
    max_len: int,
) -> list[str]:
    """去重、限长、与已有条目合并（已有条目优先保留）。"""
    result = list(existing)
    for item in raw:
        token = item.strip().strip("。，、.,;；\"'")
        if not token or len(token) > max_len:
            continue
        if token not in result:
            result.append(token)
        if len(result) >= limit:
            break
    return result[:limit]


def _call_llm(field: str, payload: AiGeneratePayload, mode: str) -> str:
    template = _FIELD_PROMPTS[field]
    instruction = template.format(
        desc_min=DESC_MIN,
        desc_max=DESC_MAX,
        prompt_max=PROMPT_MAX,
        tag_limit=TAG_LIMIT,
        tag_min=TAG_MIN_LEN,
        tag_max=TAG_MAX_LEN,
        question_limit=QUICK_QUESTION_LIMIT,
        question_max=QUESTION_MAX_LEN,
    )
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"{instruction}\n\n--- 助理信息 ---\n{_fact_block(payload, mode)}",
        },
    ]
    try:
        return llm_client.chat(messages)
    except llm_client.LlmError as exc:
        logger.warning("AI 生成失败 field=%s mode=%s：%s", field, mode, exc)
        raise BizError(
            ErrorCode.AI_GENERATE_FAILED,
            "AI 生成失败，请稍后重试",
            {"field": field, "reason": str(exc)},
            502,
        ) from exc


# ============================ 本地模板（大模型未启用时） ============================


def _split_chunk(chunk: str) -> list[str]:
    """把过长分句按连接词再切开；切不开则原样返回（由调用方按长度过滤）。"""
    if len(chunk) <= TAG_MAX_LEN:
        return [chunk]
    parts = [chunk]
    for word in _INNER_SPLITTERS:
        next_parts: list[str] = []
        for part in parts:
            next_parts.extend(part.split(word))
        parts = next_parts
    trimmed = [part for part in parts if TAG_MIN_LEN <= len(part) <= TAG_MAX_LEN]
    return trimmed or [chunk]


def _strip_verb(token: str) -> str:
    """剥掉开头的动词，让标签更像名词短语（如「解答考勤规则」→「考勤规则」）。"""
    for prefix in _VERB_PREFIXES:
        if token.startswith(prefix) and len(token) > len(prefix):
            stripped = token[len(prefix) :]
            if TAG_MIN_LEN <= len(stripped) <= TAG_MAX_LEN:
                return stripped
    return token


def _keywords(text: str, limit: int) -> list[str]:
    """从名称 / 分类 / 描述中抽取可用作标签的短词。"""
    cleaned = text
    for sep in _SEPARATORS:
        cleaned = cleaned.replace(sep, " ")
    result: list[str] = []
    for chunk in cleaned.split():
        for part in _split_chunk(chunk):
            token = _strip_verb(part)
            if token in result or not (TAG_MIN_LEN <= len(token) <= TAG_MAX_LEN):
                continue
            result.append(token)
            if len(result) >= limit:
                return result
    return result


def _name_keywords(name: str, limit: int = 3) -> list[str]:
    """名称关键词：剥离「助理 / 助手 / 智能」等后缀后再拆词。"""
    base = name.strip()
    for suffix in _NAME_SUFFIXES:
        if base.endswith(suffix) and len(base) > len(suffix):
            base = base[: -len(suffix)]
            break
    return _keywords(base, limit)


class AiGenerateService:
    def generate(self, payload: AiGeneratePayload) -> AiGenerateResult:
        mode = payload.mode
        if mode == "auto":
            has_content = (
                bool(_text(payload.current_value))
                if payload.field in ("description", "prompt")
                else bool(_items(payload.current_value))
            )
            mode = "polish" if has_content else "generate"

        handler = {
            "description": self._description,
            "tags": self._tags,
            "prompt": self._prompt,
            "quickQuestions": self._quick_questions,
        }.get(payload.field)
        if handler is None:
            raise BizError(ErrorCode.PARAM_INVALID, "field 取值不合法", {"field": "field"}, 400)

        value, hit_limit = handler(payload, mode)
        return AiGenerateResult(
            field=payload.field, mode=mode, value=value, hit_limit=hit_limit
        )

    # ============================ 描述 ============================

    def _description(self, payload: AiGeneratePayload, mode: str) -> tuple[str, bool]:
        """生成：名称 + 分类；润色：已有描述 + 名称 + 分类。"""
        current = _text(payload.current_value) or (payload.description or "").strip()

        if llm_client.is_enabled():
            raw = _call_llm("description", payload, mode)
            value = re.sub(r"\s*\n+\s*", " ", _strip_code_fence(raw)).strip()
            if len(value) > DESC_MAX:
                value = value[:DESC_MAX]
            if len(value) >= DESC_MIN:
                return value, False
            logger.warning("大模型返回描述长度不合规，回退模板：%r", value)

        return self._local_description(payload, mode, current), False

    def _local_description(
        self, payload: AiGeneratePayload, mode: str, current: str
    ) -> str:
        name = _fallback_name(payload.name)
        category = _category(payload)
        if mode == "polish" and current:
            extra = f"{category}场景下会同步标注制度依据，涉及个人数据提醒自行核对。"
            if extra in current:
                return current[:DESC_MAX]
            merged = f"{current.rstrip('。；;，, ')}。{extra}"
            if len(merged) < DESC_MIN:
                merged = f"{merged}如需人工介入，会明确提示转人工处理。"
            return merged[:DESC_MAX]
        return (
            f"「{name}」面向{category}场景，可解答常见问题、讲解制度要点并给出办理指引；"
            "回答先给结论、再附依据，涉及个人数据时提醒员工自行核对，无法确认时明确提示转人工处理。"
        )[:DESC_MAX]

    # ============================ 自定义标签 ============================

    def _tags(self, payload: AiGeneratePayload, mode: str) -> tuple[list[str], bool]:
        """生成：名称 + 分类 + 描述；润色：已有标签保留并补足至 5 个。"""
        existing = _items(payload.current_value)
        if len(existing) >= TAG_LIMIT:
            return existing[:TAG_LIMIT], True

        if llm_client.is_enabled():
            raw = _call_llm("tags", payload, mode)
            merged = _clean_string_list(
                _parse_string_list(raw),
                existing=existing,
                limit=TAG_LIMIT,
                max_len=TAG_MAX_LEN,
            )
            if len(merged) >= min(len(existing) + 1, TAG_LIMIT):
                # 模型给的数量不足时用通用标签补齐，保证始终给出 5 个
                for token in TAG_FALLBACKS:
                    if len(merged) >= TAG_LIMIT:
                        break
                    if token not in merged:
                        merged.append(token)
                return merged[:TAG_LIMIT], False
            logger.warning("大模型返回标签不足，回退模板：%r", raw)

        return self._local_tags(payload, existing), False

    def _local_tags(self, payload: AiGeneratePayload, existing: list[str]) -> list[str]:
        name = _fallback_name(payload.name)
        category = _category(payload)
        description = (payload.description or "").strip()

        # 描述最能反映业务特征，其次名称，最后分类
        candidates = _keywords(description, 4) + _name_keywords(name, 2) + _keywords(category, 2)
        candidates.extend(TAG_FALLBACKS)

        result = list(existing)
        for token in candidates:
            if len(result) >= TAG_LIMIT:
                break
            if token and len(token) <= TAG_MAX_LEN and token not in result:
                result.append(token)
        return result[:TAG_LIMIT]

    # ============================ 提示词 ============================

    def _prompt(self, payload: AiGeneratePayload, mode: str) -> tuple[str, bool]:
        """生成：名称 + 描述 + 分类 + 标签；润色：已有提示词 + 名称 + 描述。"""
        current = _text(payload.current_value) or (payload.prompt or "").strip()

        if llm_client.is_enabled():
            raw = _strip_code_fence(_call_llm("prompt", payload, mode))
            value = raw.strip()[:PROMPT_MAX]
            if len(value) >= DESC_MIN:
                return value, False
            logger.warning("大模型返回提示词长度不合规，回退模板：%r", value)

        return self._local_prompt(payload, mode, current), False

    def _local_prompt(self, payload: AiGeneratePayload, mode: str, current: str) -> str:
        name = _fallback_name(payload.name)
        category = _category(payload)
        description = (payload.description or "").strip()
        tags = [tag.strip() for tag in payload.tags if tag.strip()][:TAG_LIMIT]

        if mode == "polish" and current:
            scope = description or f"{category}日常业务"
            tail = (
                f"补充要求：回答时结合「{name}」的服务范围（{scope}），先确认关键前提；"
                "涉及跨部门流程时给出责任部门，信息不足时先追问再作答。"
            )
            if tail in current:
                return current[:PROMPT_MAX]
            return f"{current.rstrip()}\n{tail}"[:PROMPT_MAX]

        sections = [f"你是{category}的「{name}」，负责解答{category}相关问题。"]
        if description:
            sections.append(f"服务背景：{description}")
        if tags:
            sections.append(f"擅长方向：{'、'.join(tags)}")
        sections.append(
            "回答要求：\n"
            "1. 先给结论，再给出对应的制度或流程依据；\n"
            "2. 涉及员工个人数据时，提示员工自行核对；\n"
            "3. 无法确认的问题必须说明「需人工确认」，不得编造条款编号；\n"
            "4. 需要走流程的场景，明确指引对应的审批入口。"
        )
        return "\n".join(sections)[:PROMPT_MAX]

    # ============================ 召唤快速问题 ============================

    def _quick_questions(
        self, payload: AiGeneratePayload, mode: str
    ) -> tuple[list[str], bool]:
        """生成：名称 + 描述；润色：已有问题保留并补足至 6 条。"""
        existing = _items(payload.current_value)
        if len(existing) >= QUICK_QUESTION_LIMIT:
            return existing[:QUICK_QUESTION_LIMIT], True

        if llm_client.is_enabled():
            raw = _call_llm("quickQuestions", payload, mode)
            merged = _clean_string_list(
                _parse_string_list(raw),
                existing=existing,
                limit=QUICK_QUESTION_LIMIT,
                max_len=QUESTION_MAX_LEN,
            )
            if len(merged) > len(existing):
                return merged, False
            logger.warning("大模型返回快速问题不足，回退模板：%r", raw)

        return self._local_quick_questions(payload, existing), False

    def _local_quick_questions(
        self, payload: AiGeneratePayload, existing: list[str]
    ) -> list[str]:
        name = _fallback_name(payload.name)
        description = (payload.description or "").strip()

        candidates = [
            f"{name}能帮我做什么？",
            f"如何正确使用「{name}」？",
            f"{name}常见问题有哪些？",
            f"{name}的回答依据是什么？",
        ]
        # 描述关键词用于生成更贴合业务的问题
        for keyword in _keywords(description, 2):
            candidates.append(f"{keyword}相关流程如何办理？")
        candidates.extend(
            [
                "对应的制度依据是哪一条？",
                "办理需要准备哪些材料？",
                "出现异常时应该怎么处理？",
                "处理时限是怎么规定的？",
            ]
        )

        result = list(existing)
        for question in candidates:
            if len(result) >= QUICK_QUESTION_LIMIT:
                break
            question = question[:QUESTION_MAX_LEN]
            if question not in result:
                result.append(question)
        return result[:QUICK_QUESTION_LIMIT]
