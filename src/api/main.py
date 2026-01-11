"""
新闻态势分析系统 FastAPI 主应用
工业级 RESTful API 架构
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.schemas import (
    APIException,
    BadRequestException,
    ConflictException,
    InternalServerException,
    NotFoundException,
    UnprocessableEntityException,
)
from src.core.config import settings


logger = logging.getLogger(__name__)


# ============================================================================
# 生命周期管理
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """应用生命周期管理"""
    logger.info("Starting 新闻态势分析系统 API...")

    # 启动时的初始化逻辑
    # 初始化数据库连接池和表
    from src.core.database import init_database
    await init_database()
    logger.info("数据库初始化完成")

    # 启动调度器
    from src.services.scheduler_service import start_scheduler
    await start_scheduler()
    logger.info("定时任务调度器已启动")

    yield

    logger.info("Shutting down 新闻态势分析系统 API...")

    # 关闭时的清理逻辑
    # TODO: 关闭数据库连接
    # TODO: 关闭 AI 客户端
    # TODO: 关闭搜索引擎

    # 停止调度器
    from src.services.scheduler_service import stop_scheduler
    await stop_scheduler()
    logger.info("定时任务调度器已停止")


# ============================================================================
# FastAPI 应用
# ============================================================================

app = FastAPI(
    title="新闻态势分析系统 API",
    description="新闻态势分析系统 RESTful 接口",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ============================================================================
# CORS 配置
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if hasattr(settings, "CORS_ORIGINS") else ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# 全局异常处理器
# ============================================================================


@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """自定义 API 异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Pydantic 验证错误处理"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": exc.errors()},
            },
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """通用异常处理"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"detail": str(exc)} if settings.DEBUG else None,
            },
        },
    )


# ============================================================================
# 根路由
# ============================================================================


@app.get("/api/health")
@app.get("/api/v1/health")
async def health_check():
    """健康检查"""
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "version": "2.0.0",
            "service": "newssys-api",
        },
    }


@app.get("/")
async def root():
    """根路由"""
    return {
        "success": True,
        "data": {
            "message": "新闻态势分析系统 API",
            "version": "2.0.0",
            "docs": "/api/docs",
        },
    }


@app.post("/api/")
@app.post("/api/v1/")
async def api_root():
    """API 根路由 POST"""
    return {
        "success": True,
        "data": {
            "message": "新闻态势分析系统 API v1",
            "version": "2.0.0",
            "docs": "/api/docs",
        },
    }


# ============================================================================
# 路由注册
# ============================================================================

from src.api.v1 import sources, articles, reports, search, dashboard, sitemaps, tasks, conversations, schedules, keywords, scheduler, auth, users

# 导入任务执行器（注册执行器）
from src.services import task_executors  # noqa: F401

# API v1 路由
app.include_router(
    sources.router,
    prefix="/api/v1/sources",
    tags=["sources"],
)

app.include_router(
    articles.router,
    prefix="/api/v1/articles",
    tags=["articles"],
)

app.include_router(
    reports.router,
    prefix="/api/v1/reports",
    tags=["reports"],
)

app.include_router(
    search.router,
    prefix="/api/v1/search",
    tags=["search"],
)

app.include_router(
    dashboard.router,
    prefix="/api/v1/dashboard",
    tags=["dashboard"],
)

app.include_router(
    sitemaps.router,
    prefix="/api/v1/sitemaps",
    tags=["sitemaps"],
)

app.include_router(
    tasks.router,
    prefix="/api/v1/tasks",
    tags=["tasks"],
)

app.include_router(
    conversations.router,
    prefix="/api/v1/conversations",
    tags=["conversations"],
)

app.include_router(
    schedules.router,
    prefix="/api/v1",
    tags=["schedules"],
)

app.include_router(
    keywords.router,
    prefix="/api/v1",
    tags=["keywords"],
)

app.include_router(
    scheduler.router,
    prefix="/api/v1",
    tags=["scheduler"],
)

app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["auth"],
)

app.include_router(
    users.router,
    prefix="/api/v1",
    tags=["users"],
)
