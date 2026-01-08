"""
数据库连接管理模块
提供异步数据库连接池和会话管理
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from .config import get_settings


class DatabaseManager:
    """
    数据库管理器
    负责创建和管理数据库连接池
    """

    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        """获取数据库引擎"""
        if self._engine is None:
            raise RuntimeError("Database engine not initialized. Call connect() first.")
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """获取会话工厂"""
        if self._session_factory is None:
            raise RuntimeError("Session factory not initialized. Call connect() first.")
        return self._session_factory

    def connect(self, settings: Any | None = None) -> None:
        """
        初始化数据库连接

        Args:
            settings: 配置对象，默认使用 get_settings()
        """
        if settings is None:
            settings = get_settings()

        db_config = settings.db

        engine_kwargs: dict[str, Any] = {
            "echo": db_config.echo,
            "pool_pre_ping": True,
            "pool_recycle": db_config.pool_recycle,
        }

        # 在测试环境使用 NullPool
        if settings.app.environment == "testing":
            engine_kwargs["poolclass"] = NullPool
        else:
            engine_kwargs["pool_size"] = db_config.pool_size
            engine_kwargs["max_overflow"] = db_config.max_overflow

        self._engine = create_async_engine(db_config.url, **engine_kwargs)

        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    async def disconnect(self) -> None:
        """关闭数据库连接"""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        获取数据库会话的上下文管理器

        Yields:
            AsyncSession: 数据库会话

        Example:
            async with db_manager.session() as session:
                await session.execute(...)
        """
        if self._session_factory is None:
            raise RuntimeError("Session factory not initialized. Call connect() first.")

        async with self._session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def get_session(self) -> AsyncSession:
        """
        获取数据库会话
        注意：调用者需要负责关闭会话

        Returns:
            AsyncSession: 数据库会话
        """
        if self._session_factory is None:
            raise RuntimeError("Session factory not initialized. Call connect() first.")

        return self._session_factory()


# 全局数据库管理器实例
db_manager: DatabaseManager = DatabaseManager()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    依赖注入函数：获取数据库会话
    主要用于 FastAPI 等框架的依赖注入

    Yields:
        AsyncSession: 数据库会话
    """
    async with db_manager.session() as session:
        yield session


async def init_db() -> None:
    """初始化数据库连接"""
    db_manager.connect()


async def close_db() -> None:
    """关闭数据库连接"""
    await db_manager.disconnect()
