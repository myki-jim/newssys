"""
数据库连接管理
使用 SQLAlchemy 2.0 (Async)
支持 SQLite (开发) 和 MySQL/aiomysql (生产)
"""

import logging
import asyncio
from contextlib import asynccontextmanager

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings
from src.core.orm_models import Base

logger = logging.getLogger(__name__)

# 全局引擎和会话工厂
_engine = None
_async_session_factory = None


async def _sqlite_table_columns(conn, table_name: str) -> set[str]:
    """读取 SQLite 表字段集合。"""
    result = await conn.execute(text(f"PRAGMA table_info({table_name})"))
    return {row[1] for row in result.fetchall()}


async def _ensure_sqlite_reports_schema(conn) -> None:
    """确保 SQLite 中 reports 相关表和缺失字段存在。"""
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS report_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            system_prompt TEXT NOT NULL,
            section_template TEXT DEFAULT '[]',
            is_default INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))

    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            time_range_start TIMESTAMP NOT NULL,
            time_range_end TIMESTAMP NOT NULL,
            template_id INTEGER,
            custom_prompt TEXT,
            language TEXT DEFAULT 'zh',
            max_events INTEGER DEFAULT 10,
            total_articles INTEGER DEFAULT 0,
            clustered_articles INTEGER DEFAULT 0,
            event_count INTEGER DEFAULT 0,
            content TEXT,
            sections TEXT DEFAULT '[]',
            status TEXT DEFAULT 'draft',
            agent_stage TEXT DEFAULT 'initializing',
            agent_progress INTEGER DEFAULT 0,
            agent_message TEXT DEFAULT '',
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (template_id) REFERENCES report_templates(id) ON DELETE SET NULL
        )
    """))

    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS report_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            event_title TEXT NOT NULL,
            event_summary TEXT,
            article_count INTEGER DEFAULT 0,
            keywords TEXT DEFAULT '[]',
            importance_score REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
        )
    """))

    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS report_sections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            section_title TEXT NOT NULL,
            section_content TEXT,
            section_order INTEGER DEFAULT 0,
            event_ids TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
        )
    """))

    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS report_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            article_id INTEGER NOT NULL,
            event_id INTEGER,
            is_representative INTEGER DEFAULT 0,
            citation_index INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
            FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
            FOREIGN KEY (event_id) REFERENCES report_events(id) ON DELETE SET NULL
        )
    """))

    report_columns = await _sqlite_table_columns(conn, "reports")
    if "max_events" not in report_columns:
        await conn.execute(text("ALTER TABLE reports ADD COLUMN max_events INTEGER DEFAULT 10"))
        logger.info("SQLite schema upgraded: added reports.max_events")

    if "sections" not in report_columns:
        await conn.execute(text("ALTER TABLE reports ADD COLUMN sections TEXT DEFAULT '[]'"))
        logger.info("SQLite schema upgraded: added reports.sections")

    if "agent_progress" not in report_columns:
        await conn.execute(text("ALTER TABLE reports ADD COLUMN agent_progress INTEGER DEFAULT 0"))
        logger.info("SQLite schema upgraded: added reports.agent_progress")

    if "agent_message" not in report_columns:
        await conn.execute(text("ALTER TABLE reports ADD COLUMN agent_message TEXT DEFAULT ''"))
        logger.info("SQLite schema upgraded: added reports.agent_message")

    if "clustered_articles" not in report_columns:
        await conn.execute(text("ALTER TABLE reports ADD COLUMN clustered_articles INTEGER DEFAULT 0"))
        logger.info("SQLite schema upgraded: added reports.clustered_articles")

    if "event_count" not in report_columns:
        await conn.execute(text("ALTER TABLE reports ADD COLUMN event_count INTEGER DEFAULT 0"))
        logger.info("SQLite schema upgraded: added reports.event_count")


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
            "connect_args": {"timeout": settings.database.sqlite_timeout},
        }
    else:
        logger.info(f"Connecting to MySQL: {settings.database.name} @ {settings.database.host}")
        engine_kwargs = {
            "echo": settings.debug,
            "pool_size": settings.database.pool_size,
            "max_overflow": settings.database.max_overflow,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
            "connect_args": {"charset": "utf8mb4"},
        }

    _engine = create_async_engine(settings.database.url, **engine_kwargs)

    if settings.database.type == "sqlite":
        @event.listens_for(_engine.sync_engine, "connect")
        def _configure_sqlite(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            try:
                # WAL improves read/write concurrency for local development.
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.execute(f"PRAGMA busy_timeout={settings.database.sqlite_busy_timeout_ms};")
                cursor.execute("PRAGMA foreign_keys=ON;")
            finally:
                cursor.close()

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
            await asyncio.shield(session.rollback())
            raise
        finally:
            await asyncio.shield(session.close())


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
        WorkerHeartbeatOrm,
    )

    init_engine()

    if _engine is None:
        raise RuntimeError("Database engine not initialized")

    # 创建所有表
    async with _engine.begin() as conn:
        if settings.database.type == "sqlite":
            await conn.execute(text("PRAGMA journal_mode=WAL;"))
            await conn.execute(text(f"PRAGMA busy_timeout={settings.database.sqlite_busy_timeout_ms};"))
            await _ensure_sqlite_reports_schema(conn)
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
