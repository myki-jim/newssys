"""
SQLAlchemy ORM 模型定义
用于数据库表创建和 ORM 操作
"""

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


class ArticleStatus(str, Enum):
    """文章状态枚举"""
    RAW = "raw"
    PROCESSED = "processed"
    SYNCED = "synced"
    FAILED = "failed"


class FetchStatus(str, Enum):
    """抓取任务状态枚举"""
    PENDING = "pending"
    SUCCESS = "success"
    RETRY = "retry"
    FAILED = "failed"


class RobotsStatus(str, Enum):
    """Robots.txt 状态枚举"""
    PENDING = "pending"
    COMPLIANT = "compliant"
    RESTRICTED = "restricted"
    NOT_FOUND = "not_found"
    ERROR = "error"


class CrawlSourceOrm(Base):
    """爬虫源 ORM 模型"""
    __tablename__ = "crawl_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    parser_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default={})
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    crawl_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)

    # Robots.txt 相关
    robots_status: Mapped[RobotsStatus] = mapped_column(
        SQLEnum(RobotsStatus), nullable=False, default=RobotsStatus.PENDING
    )
    crawl_delay: Mapped[int | None] = mapped_column(Integer, nullable=True)
    robots_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Sitemap 相关
    sitemap_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sitemap_last_fetched: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sitemap_entry_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 统计信息
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 发现策略
    discovery_method: Mapped[str] = mapped_column(
        String(50), nullable=False, default="sitemap"
    )

    # 灵活元数据
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )


class ArticleOrm(Base):
    """文章 ORM 模型"""
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 内容版本化
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    publish_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # 双重状态
    status: Mapped[ArticleStatus] = mapped_column(
        SQLEnum(ArticleStatus), nullable=False, default=ArticleStatus.RAW
    )
    fetch_status: Mapped[FetchStatus] = mapped_column(
        SQLEnum(FetchStatus), nullable=False, default=FetchStatus.PENDING
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)

    crawled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 重试机制
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 灵活元数据
    extra_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )


class ReportMetadataOrm(Base):
    """报告元数据 ORM 模型"""
    __tablename__ = "report_metadata"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    template_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    time_range: Mapped[str | None] = mapped_column(String(50), nullable=True)
    article_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")

    # 报告内容（Markdown 格式）
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    extra_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )


class ReportReferenceOrm(Base):
    """报告引用 ORM 模型"""
    __tablename__ = "report_references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    article_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    citation_index: Mapped[int] = mapped_column(Integer, nullable=False)
    context_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    citation_position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )


# 导出模型列表
__all__ = [
    "Base",
    "CrawlSourceOrm",
    "ArticleOrm",
    "ReportMetadataOrm",
    "ReportReferenceOrm",
    "SitemapOrm",
    "PendingArticleOrm",
    "TaskOrm",
    "ScheduleOrm",
    "SearchKeywordOrm",
]


class SitemapFetchStatus(str, Enum):
    """Sitemap 抓取状态枚举"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class PendingArticleStatus(str, Enum):
    """待爬文章状态枚举"""
    PENDING = "pending"
    CRAWLING = "crawling"
    COMPLETED = "completed"
    FAILED = "failed"
    ABANDONED = "abandoned"  # 已遗弃（重试失败后不再处理）
    LOW_QUALITY = "low_quality"  # 低质量（标记为低质量，不再爬取）


class SitemapOrm(Base):
    """Sitemap ORM 模型"""
    __tablename__ = "sitemaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    last_fetched: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetch_status: Mapped[SitemapFetchStatus] = mapped_column(
        SQLEnum(SitemapFetchStatus), nullable=False, default=SitemapFetchStatus.PENDING
    )
    article_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )


class PendingArticleOrm(Base):
    """待爬文章 ORM 模型"""
    __tablename__ = "pending_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sitemap_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publish_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[PendingArticleStatus] = mapped_column(
        SQLEnum(PendingArticleStatus), nullable=False, default=PendingArticleStatus.PENDING
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskEventType(str, Enum):
    """任务事件类型枚举"""
    CREATED = "created"
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INFO = "info"


class TaskOrm(Base):
    """任务 ORM 模型"""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus), nullable=False, default=TaskStatus.PENDING, index=True
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    params: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    result: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    progress_current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )


class TaskEventOrm(Base):
    """任务事件 ORM 模型"""
    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    event_type: Mapped[TaskEventType] = mapped_column(
        SQLEnum(TaskEventType), nullable=False
    )
    event_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, index=True
    )


class ConversationOrm(Base):
    """对话 ORM 模型"""
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="新对话")
    mode: Mapped[str] = mapped_column(String(50), nullable=False, default="chat")
    web_search_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    internal_search_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    # 关系
    messages: Mapped[list["MessageOrm"]] = relationship(
        "MessageOrm", back_populates="conversation", cascade="all, delete-orphan"
    )


class MessageOrm(Base):
    """消息 ORM 模型"""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_state: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    search_results: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, index=True
    )

    # 关系
    conversation: Mapped["ConversationOrm"] = relationship(
        "ConversationOrm", back_populates="messages"
    )


class ScheduleType(str, Enum):
    """定时任务类型枚举"""
    SITEMAP_CRAWL = "sitemap_crawl"  # Sitemap爬取
    ARTICLE_CRAWL = "article_crawl"  # 文章自动爬取
    KEYWORD_SEARCH = "keyword_search"  # 关键词搜索


class ScheduleStatus(str, Enum):
    """定时任务状态枚举"""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class ScheduleOrm(Base):
    """定时任务 ORM 模型"""
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    schedule_type: Mapped[ScheduleType] = mapped_column(
        SQLEnum(ScheduleType), nullable=False, index=True
    )
    status: Mapped[ScheduleStatus] = mapped_column(
        SQLEnum(ScheduleStatus), nullable=False, default=ScheduleStatus.ACTIVE
    )

    # 调度配置
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)  # 执行间隔（分钟）
    max_executions: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 最大执行次数，None表示无限
    execution_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 已执行次数

    # 关联配置（JSON格式）
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # 示例：
    # sitemap_crawl: {"source_id": 1, "sitemap_id": 6}
    # article_crawl: {"batch_size": 50}
    # keyword_search: {"keyword_id": 1, "time_range": "w", "max_results": 10, "region": "us-en"}

    # 执行统计
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    last_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # success, failed
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )


class SearchKeywordOrm(Base):
    """搜索关键词 ORM 模型"""
    __tablename__ = "search_keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 搜索配置
    time_range: Mapped[str] = mapped_column(String(10), nullable=False, default="w")  # d, w, m, y
    max_results: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    region: Mapped[str] = mapped_column(String(10), nullable=False, default="us-en")

    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # 统计
    search_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_searched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )


class UserRole(str, Enum):
    """用户角色枚举"""
    ADMIN = "admin"  # 管理员，可以管理用户
    USER = "user"    # 普通用户


class UserOrm(Base):
    """用户 ORM 模型"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)  # 明文存储
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), nullable=False, default=UserRole.USER)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    office: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 办公室编号

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )
