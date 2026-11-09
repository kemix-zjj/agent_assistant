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
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="助理团助理创建与共享授权 · 后端服务",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        default_response_class=UnifiedJSONResponse,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TraceMiddleware)

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.api_prefix)

    # 本地头像存储（生产环境替换为对象存储域名）
    static_dir = settings.static_dir
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

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

    return app


app = create_app()
