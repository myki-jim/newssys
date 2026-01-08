"""
数据库连接管理
使用 SQLAlchemy 2.0 (Async)
支持 SQLite (开发) 和 MySQL/aiomysql (生产)
"""

import logging
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings
from src.core.orm_models import Base

logger = logging.getLogger(__name__)

# 全局引擎和会话工厂
_engine = None
_async_session_factory = None


def init_engine():
    """初始化数据库引擎（支持 SQLite 和 MySQL）"""
    global _engine, _async_session_factory

    if _engine is not None:
        return _engine

    # 根据数据库类型构建引擎参数
    if settings.database.type == "sqlite":
        logger.info(f"Connecting to SQLite: {settings.database.name}")
        engine_kwargs = {
            "echo": settings.debug,
        }
    else:
        logger.info(f"Connecting to MySQL: {settings.database.name} @ {settings.database.host}")
        engine_kwargs = {
            "echo": settings.debug,
            "pool_size": settings.database.pool_size,
            "max_overflow": settings.database.max_overflow,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
        }

    _engine = create_async_engine(settings.database.url, **engine_kwargs)

    _async_session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    logger.info("Database engine initialized")
    return _engine


async def close_engine():
    """关闭数据库引擎"""
    global _engine, _async_session_factory

    if _engine is None:
        return

    logger.info("Closing database connection...")
    await _engine.dispose()
    _engine = None
    _async_session_factory = None


@asynccontextmanager
async def get_async_session():
    """获取异步数据库会话（上下文管理器）"""
    if _async_session_factory is None:
        init_engine()

    async with _async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_async_session_generator():
    """获取异步数据库会话（生成器，用于依赖注入）"""
    if _async_session_factory is None:
        init_engine()

    return _async_session_factory()


async def init_database():
    """初始化数据库（创建表）"""
    from src.core.orm_models import (
        ArticleOrm,
        CrawlSourceOrm,
        ReportMetadataOrm,
        ReportReferenceOrm,
    )

    init_engine()

    if _engine is None:
        raise RuntimeError("Database engine not initialized")

    # 创建所有表
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created successfully")


__all__ = [
    "Base",
    "init_engine",
    "close_engine",
    "get_async_session",
    "get_async_session_generator",
    "init_database",
]
