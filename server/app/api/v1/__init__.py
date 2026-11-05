"""v1 路由汇总。新增业务模块时在此注册。"""

from fastapi import APIRouter

from app.api.v1 import ai, approvals, assistants, categories, common, resources, scopes, shares

api_router = APIRouter()
# 助理详情为 /assistants/{id}，共享范围子路径需先注册以免被通配匹配
api_router.include_router(shares.router)
api_router.include_router(approvals.router)
api_router.include_router(assistants.router)
api_router.include_router(scopes.router)
api_router.include_router(resources.router)
api_router.include_router(categories.router)
api_router.include_router(ai.router)
api_router.include_router(common.router)
