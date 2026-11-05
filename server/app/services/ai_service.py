"""AI 生成服务（对应 docs/03 §8.1）。

当前未接入大模型中台，采用确定性模板实现，保证：
- 输出符合各字段校验规则（描述 10-200 字、单标签 ≤8 字且 ≤5 个、
  提示词 ≤4000 字、快速问题 ≤6 条去重）；
- 区分 generate（字段为空）与 polish（已有内容）两种模式；
- 标签 / 快速问题已满时返回 hitLimit=true 且 value 为原值。

接入真实大模型时，替换 _generate / _polish 内部实现即可，
路由与服务签名不需要改。
"""

from app.core.errors import BizError, ErrorCode
from app.schemas.common import AiGeneratePayload, AiGenerateResult

TAG_LIMIT = 5
QUICK_QUESTION_LIMIT = 6
DESC_MIN, DESC_MAX = 10, 200
TAG_MAX_LEN = 8
PROMPT_MAX = 4000


def _fallback_name(name: str) -> str:
    return name.strip() or "业务助理"


def _category(payload: AiGeneratePayload) -> str:
    return (payload.category_name or "本部门").strip()


def _current_text(value: str | list[str] | None) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _current_list(value: str | list[str] | None, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        return [item.strip() for item in value if item.strip()]
    return list(fallback)


class AiGenerateService:
    def generate(self, payload: AiGeneratePayload) -> AiGenerateResult:
        mode = payload.mode
        if mode == "auto":
            has_content = (
                bool(_current_text(payload.current_value))
                if payload.field in ("description", "prompt")
                else bool(_current_list(payload.current_value, []))
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

    # ============================ 各字段 ============================

    def _description(
        self, payload: AiGeneratePayload, mode: str
    ) -> tuple[str, bool]:
        name = _fallback_name(payload.name)
        category = _category(payload)

        if mode == "polish":
            base = _current_text(payload.current_value) or payload.description or ""
            if not base:
                return self._description(payload, "generate")
            # 润色：保留原意，补充场景与依据说明
            extra = f"可结合{category}的制度条款与业务数据给出可执行建议，并标注依据来源。"
            merged = base if extra in base else f"{base.rstrip('。')}。{extra}"
            return merged[:DESC_MAX], False

        tags = payload.tags[:3] if payload.tags else []
        keyword = "、".join(tags) if tags else category
        value = (
            f"{name}面向{category}的日常业务场景，围绕{keyword}提供问答与操作指引，"
            "输出结论时同步标注制度依据，涉及个人数据会提示自行核对。"
        )
        return value[:DESC_MAX], False

    def _tags(self, payload: AiGeneratePayload, mode: str) -> tuple[list[str], bool]:
        existing = _current_list(payload.current_value, payload.tags)
        if len(existing) >= TAG_LIMIT:
            return existing[:TAG_LIMIT], True

        name = _fallback_name(payload.name)
        category = _category(payload)
        description = (payload.description or "").strip()

        candidates: list[str] = []
        for source in (category, name, description):
            for token in _split_tokens(source):
                if token not in candidates:
                    candidates.append(token)

        candidates.extend(["业务问答", "制度检索", "流程指引", "数据分析", "风险提示"])

        result = list(existing)
        for token in candidates:
            if len(result) >= TAG_LIMIT:
                break
            if token and len(token) <= TAG_MAX_LEN and token not in result:
                result.append(token)
        return result[:TAG_LIMIT], False

    def _prompt(self, payload: AiGeneratePayload, mode: str) -> tuple[str, bool]:
        name = _fallback_name(payload.name)
        category = _category(payload)
        description = (payload.description or "").strip()

        if mode == "polish":
            base = _current_text(payload.current_value) or payload.prompt or ""
            if base:
                tail = "补充要求：回答前先确认关键前提，涉及跨部门流程时给出责任部门。"
                merged = base if tail in base else f"{base.rstrip()}\n{tail}"
                return merged[:PROMPT_MAX], False

        rules = (
            "回答要求：先给结论，再给制度依据；涉及个人数据须提示自行核对；"
            "无法确认时说明「需人工确认」，不得编造条款编号。"
        )
        context = f"背景：{description}" if description else f"服务范围：{category}"
        value = (
            f"你是{category}的{name}，负责解答{category}相关问题。\n"
            f"{context}\n"
            f"{rules}"
        )
        return value[:PROMPT_MAX], False

    def _quick_questions(
        self, payload: AiGeneratePayload, mode: str
    ) -> tuple[list[str], bool]:
        existing = _current_list(payload.current_value, payload.quick_questions)
        if len(existing) >= QUICK_QUESTION_LIMIT:
            return existing[:QUICK_QUESTION_LIMIT], True

        category = _category(payload)
        candidates = [
            f"{category}相关流程需要哪些审批？",
            "对应的制度依据是哪一条？",
            "出现异常时应该怎么处理？",
            "需要准备哪些材料？",
            "处理时限是怎么规定的？",
            "有哪些常见风险需要规避？",
        ]

        result = list(existing)
        for question in candidates:
            if len(result) >= QUICK_QUESTION_LIMIT:
                break
            if question not in result:
                result.append(question)
        return result[:QUICK_QUESTION_LIMIT], False


def _split_tokens(text: str) -> list[str]:
    """把名称/描述拆成可用作标签的短词。"""
    separators = "，。、；：（）()· \n\t/-"
    cleaned = text
    for sep in separators:
        cleaned = cleaned.replace(sep, " ")
    return [token for token in cleaned.split(" ") if 2 <= len(token) <= TAG_MAX_LEN]
