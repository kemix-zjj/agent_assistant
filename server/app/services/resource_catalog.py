"""平台资源目录（SKILL / MCP / 知识库）。

本期这些资源由平台侧维护，不在本服务落库；助理保存时按此处目录校验并取名称快照。
接入真实资源中心后，替换本模块的查询函数即可，服务层无需改动。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceItem:
    id: str
    name: str
    desc: str = ""
    # internal 集团自研 / external 生态市场
    market: str = "internal"


@dataclass(frozen=True)
class McpResourceItem(ResourceItem):
    type: str = ""


@dataclass(frozen=True)
class KnowledgeBaseItem(ResourceItem):
    document_count: int = 0
    files: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "documentCount": self.document_count,
            "market": self.market,
            "files": list(self.files),
        }


SKILLS: tuple[ResourceItem, ...] = (
    ResourceItem("s1", "简历初筛", "按岗位画像对候选人简历打分并输出匹配结论"),
    ResourceItem("s2", "面试提纲生成", "依据岗位胜任力模型生成结构化面试题"),
    ResourceItem("s3", "薪资结构解析", "拆解工资条结构并定位异常项"),
    ResourceItem("s4", "制度条款检索", "按问题检索制度原文并给出来源条款"),
    ResourceItem("s5", "巡检清单生成", "按厂区与设备类型生成巡检项清单"),
    ResourceItem("s6", "会议纪要提炼", "从会议记录中提炼结论、待办与责任人", "external"),
    ResourceItem("s7", "报价单校验", "按价格政策校验报价单合规性", "external"),
    ResourceItem("s8", "培训课件生成", "按培训主题生成课件大纲与练习题", "external"),
    ResourceItem("s9", "表格数据处理", "按指令完成表格清洗、汇总与图表建议", "external"),
    ResourceItem("s10", "日程会议安排", "解析自然语言生成日程与会议邀请", "external"),
)

MCPS: tuple[McpResourceItem, ...] = (
    McpResourceItem("m1", "企业微信通讯录", type="组织数据"),
    McpResourceItem("m2", "HR 主数据服务", type="业务系统"),
    McpResourceItem("m3", "考勤打卡服务", type="业务系统"),
    McpResourceItem("m4", "薪酬核算服务", type="业务系统"),
    McpResourceItem("m5", "WMS 仓储服务", market="external", type="业务系统"),
    McpResourceItem("m6", "隐患台账服务", market="external", type="业务系统"),
    McpResourceItem("m7", "飞书多维表格", market="external", type="第三方应用"),
    McpResourceItem("m8", "钉钉待办", market="external", type="第三方应用"),
)

KNOWLEDGE_BASES: tuple[KnowledgeBaseItem, ...] = (
    KnowledgeBaseItem(
        "k1",
        "招聘管理制度库",
        document_count=128,
        files=("招聘管理办法.pdf", "面试评估操作指引.docx", "校园招聘流程.pdf"),
    ),
    KnowledgeBaseItem(
        "k2",
        "薪酬福利政策库",
        document_count=96,
        files=("薪酬结构管理办法.pdf", "个税专项附加扣除指引.pdf", "社保公积金缴纳标准.xlsx"),
    ),
    KnowledgeBaseItem(
        "k3",
        "员工考勤制度库",
        document_count=64,
        files=("考勤管理制度.pdf", "请假与调休细则.docx", "加班管理规定.pdf"),
    ),
    KnowledgeBaseItem(
        "k4",
        "仓储作业规范库",
        document_count=212,
        files=("仓储盘点作业指导书.pdf", "库区安全管理规范.pdf", "出入库操作手册.docx"),
    ),
    KnowledgeBaseItem(
        "k5",
        "环安法规与标准库",
        document_count=158,
        files=("安全生产法（2021）.pdf", "隐患排查治理标准.docx", "环保合规清单.xlsx"),
    ),
    KnowledgeBaseItem(
        "k6",
        "报价政策库",
        document_count=43,
        files=("价格政策管理办法.pdf", "折扣审批权限表.xlsx"),
    ),
)

_SKILL_MAP = {item.id: item for item in SKILLS}
_MCP_MAP = {item.id: item for item in MCPS}
_KB_MAP = {item.id: item for item in KNOWLEDGE_BASES}


def _match(keyword: str | None, items: tuple[ResourceItem, ...]) -> list[ResourceItem]:
    if not keyword:
        return list(items)
    kw = keyword.strip()
    if not kw:
        return list(items)
    return [item for item in items if kw in item.name or kw in item.desc]


def search_skills(keyword: str | None = None) -> list[ResourceItem]:
    return _match(keyword, SKILLS)


def search_mcps(keyword: str | None = None) -> list[ResourceItem]:
    return _match(keyword, MCPS)  # type: ignore[arg-type]


def search_knowledge_bases(keyword: str | None = None) -> list[ResourceItem]:
    return _match(keyword, KNOWLEDGE_BASES)


def find_skills(ids: list[str]) -> list[ResourceItem]:
    """按 ID 顺序返回资源；任一 ID 不存在返回空列表（由服务层转 RESOURCE_UNAVAILABLE）。"""
    items = [_SKILL_MAP[i] for i in ids if i in _SKILL_MAP]
    return items if len(items) == len(ids) else []


def find_mcps(ids: list[str]) -> list[McpResourceItem]:
    items = [_MCP_MAP[i] for i in ids if i in _MCP_MAP]
    return items if len(items) == len(ids) else []


def find_knowledge_bases(ids: list[str]) -> list[ResourceItem]:
    items = [_KB_MAP[i] for i in ids if i in _KB_MAP]
    return items if len(items) == len(ids) else []


def missing_skill_ids(ids: list[str]) -> list[str]:
    return [i for i in ids if i not in _SKILL_MAP]


def missing_mcp_ids(ids: list[str]) -> list[str]:
    return [i for i in ids if i not in _MCP_MAP]


def missing_kb_ids(ids: list[str]) -> list[str]:
    return [i for i in ids if i not in _KB_MAP]
