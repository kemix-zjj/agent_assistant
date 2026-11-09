"""分类字典出入参（对应 docs/03 §3.9）。"""

from pydantic import BaseModel, Field


class CategoryItem(BaseModel):
    categoryId: int
    name: str
    isBuiltin: bool
    sortNo: int

    model_config = {"from_attributes": True}


class CategoryListResponse(BaseModel):
    list: list[CategoryItem]


class CategoryCreatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=10)


class CategoryUpdatePayload(BaseModel):
    name: str = Field(min_length=1, max_length=10)


class CategoryDeleteResult(BaseModel):
    categoryId: int
    deleted: bool
    affectedAssistantCount: int = 0
