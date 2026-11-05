"""资源目录服务：SKILL / MCP / 知识库候选列表（对应 docs/03 §4.3 ~ §4.5）。"""

from app.schemas.common import (
    KnowledgeBaseOut,
    McpOut,
    SkillOut,
)
from app.services import resource_catalog


def list_skills(keyword: str | None) -> list[SkillOut]:
    return [
        SkillOut(id=item.id, name=item.name, desc=item.desc, market=item.market)
        for item in resource_catalog.search_skills(keyword)
    ]


def list_mcps(keyword: str | None) -> list[McpOut]:
    return [
        McpOut(id=item.id, name=item.name, type=item.type, market=item.market)
        for item in resource_catalog.search_mcps(keyword)
    ]


def list_knowledge_bases(keyword: str | None) -> list[KnowledgeBaseOut]:
    return [
        KnowledgeBaseOut(
            id=item.id,
            name=item.name,
            document_count=item.document_count,
            market=item.market,
            files=list(item.files),
        )
        for item in resource_catalog.search_knowledge_bases(keyword)
    ]
