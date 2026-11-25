"""FastAPI 应用装配入口。

启动：uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.v1 import api_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.json_response import UnifiedJSONResponse
from app.core.logging import setup_logging
from app.core.middleware import TraceMiddleware
from app.core.response import ok

setup_logging()


def create_app() -> FastAPI:

    
# 造 app（配置 + 文档开关）
#   → 装 CORS（谁可以跨域）
#   → 装 Trace（日志与链路）
#   → 装异常处理（错误怎么统一出口）
#   → 装路由（业务能力从哪来）
#   → 装静态目录（文件从哪来）
#   → 加个自我介绍接口
#   → 返回


    # 造出应用对象
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="助理团助理创建与共享授权 · 后端服务",
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
        default_response_class=UnifiedJSONResponse,  # 所有响应的默认类，负责补 traceId
    )

    # CORS 跨域配置（端跑在`5173` ，后端在`8000` ，浏览器认为这是两个不同的源，默认会拦掉跨域请求）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # 自定义中间件（负责 traceId）
    app.add_middleware(TraceMiddleware)

    # 注册全局异常处理器
    register_exception_handlers(app)

    # 注册路由/挂载路由
    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.api_prefix)

    # 静态文件挂载 本地头像存储（生产环境替换为对象存储域名）
    static_dir = settings.static_dir
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # 根路径（返回应用信息）
    @app.get("/", include_in_schema=False)
    def index() -> dict:
        return ok(
            {
                "app": settings.app_name,
                "version": settings.app_version,
                "docs": "/docs",
                "apiPrefix": settings.api_prefix,
            }
        )
    # 返回应用对象
    return app

# 模块级实例化应用对象
app = create_app()
