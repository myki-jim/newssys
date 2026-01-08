"""
核心数据模型定义
使用 Pydantic 定义领域模型
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ArticleStatus(str, Enum):
    """文章状态枚举（语义状态）"""

    RAW = "raw"  # 原始抓取状态
    PROCESSED = "processed"  # 已处理状态
    SYNCED = "synced"  # 已同步状态
    FAILED = "failed"  # 失败状态


class FetchStatus(str, Enum):
    """抓取任务状态枚举（技术状态）"""

    PENDING = "pending"  # 待处理
    SUCCESS = "success"  # 抓取成功
    RETRY = "retry"  # 需要重试
    FAILED = "failed"  # 抓取失败


class ParserConfig(BaseModel):
    """
    解析器配置
    存储用于解析网页的选择器配置
    """

    title_selector: str = Field(description="文章标题选择器")
    content_selector: str = Field(description="文章内容选择器")
    publish_time_selector: str | None = Field(
        default=None, description="发布时间选择器"
    )
    author_selector: str | None = Field(default=None, description="作者选择器")
    list_selector: str | None = Field(default=None, description="文章列表选择器")
    url_selector: str | None = Field(default=None, description="链接选择器")
    encoding: str = Field(default="utf-8", description="网页编码")

    model_config = {"extra": "allow"}


class RobotsStatus(str, Enum):
    """Robots.txt 状态枚举"""

    PENDING = "pending"  # 待检查
    COMPLIANT = "compliant"  # 可访问，遵守规则
    RESTRICTED = "restricted"  # 有访问限制
    NOT_FOUND = "not_found"  # robots.txt 不存在
    ERROR = "error"  # 解析错误


class SitemapFetchStatus(str, Enum):
    """Sitemap 抓取状态枚举"""

    PENDING = "pending"  # 待抓取
    SUCCESS = "success"  # 抓取成功
    FAILED = "failed"  # 抓取失败


class PendingArticleStatus(str, Enum):
    """待爬文章状态枚举"""

    PENDING = "pending"  # 待爬取
    CRAWLING = "crawling"  # 爬取中
    COMPLETED = "completed"  # 已完成（已入库）
    FAILED = "failed"  # 爬取失败
    ABANDONED = "abandoned"  # 已遗弃（重试失败后不再处理）


class CrawlSource(BaseModel):
    """
    爬虫源配置模型
    定义新闻源的配置信息
    """

    id: int | None = Field(default=None, description="源 ID")
    site_name: str = Field(description="站点名称")
    base_url: str = Field(description="基础 URL")
    parser_config: ParserConfig = Field(description="解析器配置")
    enabled: bool = Field(default=False, description="是否启用（默认禁用，需要配置 Sitemap 后才能启用）")
    crawl_interval: int = Field(default=3600, description="爬取间隔（秒）")

    # Robots.txt 相关
    robots_status: RobotsStatus = Field(default=RobotsStatus.PENDING, description="Robots.txt 状态")
    crawl_delay: int | None = Field(default=None, description="Robots.txt 指定的抓取延迟（秒）")
    robots_fetched_at: datetime | None = Field(default=None, description="Robots.txt 最后获取时间")

    # Sitemap 相关
    sitemap_url: str | None = Field(default=None, description="主 Sitemap URL")
    sitemap_last_fetched: datetime | None = Field(default=None, description="Sitemap 最后获取时间")
    sitemap_entry_count: int | None = Field(default=None, description="Sitemap 条目数量")

    # 统计信息
    last_crawled_at: datetime | None = Field(default=None, description="最后爬取时间")
    success_count: int = Field(default=0, description="成功爬取次数")
    failure_count: int = Field(default=0, description="失败爬取次数")
    last_error: str | None = Field(default=None, description="最后错误信息")

    # 发现策略
    discovery_method: str = Field(default="sitemap", description="URL 发现策略: sitemap, list, hybrid")

    # 灵活元数据
    extra_data: dict[str, Any] | None = Field(default=None, description="额外元数据（JSON）")

    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """验证 base_url 格式"""
        if not v.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        return v.rstrip("/")

    @field_validator("crawl_interval")
    @classmethod
    def validate_crawl_interval(cls, v: int) -> int:
        """验证爬取间隔"""
        if v < 60:
            raise ValueError("crawl_interval must be at least 60 seconds")
        return v

    @field_validator("discovery_method")
    @classmethod
    def validate_discovery_method(cls, v: str) -> str:
        """验证发现策略"""
        if v not in ["sitemap", "list", "hybrid"]:
            raise ValueError("discovery_method must be one of: sitemap, list, hybrid")
        return v


class Article(BaseModel):
    """
    文章模型
    定义文章的基本信息
    """

    id: int | None = Field(default=None, description="文章 ID")
    url_hash: str = Field(description="URL 哈希值，用于去重")
    url: str = Field(description="文章 URL")
    title: str = Field(description="文章标题")
    content: str | None = Field(default=None, description="文章内容")

    # 内容版本化
    content_hash: str | None = Field(default=None, description="内容 SHA256 哈希，用于检测内容变化")

    publish_time: datetime | None = Field(default=None, description="发布时间")
    author: str | None = Field(default=None, description="作者")
    source_id: int = Field(description="源 ID")

    # 双重状态
    status: ArticleStatus = Field(default=ArticleStatus.RAW, description="文章语义状态")
    fetch_status: FetchStatus = Field(default=FetchStatus.PENDING, description="抓取任务状态")

    error_message: str | None = Field(default=None, description="错误信息（兼容旧字段）")
    error_msg: str | None = Field(default=None, description="错误信息（新字段，优先使用）")

    crawled_at: datetime | None = Field(default=None, description="爬取时间")
    processed_at: datetime | None = Field(default=None, description="处理时间")
    synced_at: datetime | None = Field(default=None, description="同步时间")

    # 重试机制
    retry_count: int = Field(default=0, description="重试次数")
    last_retry_at: datetime | None = Field(default=None, description="最后重试时间")

    # 灵活元数据
    extra_data: dict[str, Any] | None = Field(default=None, description="额外元数据（JSON）")

    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """验证 URL 格式"""
        if not v.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return v


class ArticleCreate(BaseModel):
    """文章创建请求模型"""

    url: str = Field(description="文章 URL")
    title: str = Field(description="文章标题")
    content: str | None = Field(default=None, description="文章内容")
    publish_time: datetime | None = Field(default=None, description="发布时间")
    author: str | None = Field(default=None, description="作者")
    source_id: int = Field(description="源 ID")
    extra_data: dict[str, Any] | None = Field(default=None, description="额外元数据（JSON）")


class ArticleUpdate(BaseModel):
    """文章更新请求模型"""

    title: str | None = Field(default=None, description="文章标题")
    content: str | None = Field(default=None, description="文章内容")
    publish_time: datetime | None = Field(default=None, description="发布时间")
    author: str | None = Field(default=None, description="作者")
    status: ArticleStatus | None = Field(default=None, description="文章状态")
    error_message: str | None = Field(default=None, description="错误信息")


class SourceCreate(BaseModel):
    """爬虫源创建请求模型"""

    site_name: str = Field(description="站点名称")
    base_url: str = Field(description="基础 URL")
    parser_config: ParserConfig = Field(description="解析器配置")
    enabled: bool = Field(default=False, description="是否启用（默认禁用，需要配置 Sitemap 后才能启用）")
    crawl_interval: int = Field(default=3600, description="爬取间隔（秒）")
    robots_status: RobotsStatus = Field(default=RobotsStatus.PENDING, description="Robots.txt 状态")
    discovery_method: str = Field(default="sitemap", description="发现策略")


class SourceUpdate(BaseModel):
    """爬虫源更新请求模型"""

    site_name: str | None = Field(default=None, description="站点名称")
    base_url: str | None = Field(default=None, description="基础 URL")
    parser_config: ParserConfig | None = Field(default=None, description="解析器配置")
    enabled: bool | None = Field(default=None, description="是否启用")
    crawl_interval: int | None = Field(default=None, description="爬取间隔（秒）")


# ============================================================================
# Sitemap 相关模型
# ============================================================================


class Sitemap(BaseModel):
    """Sitemap 模型"""

    id: int | None = Field(default=None, description="Sitemap ID")
    source_id: int = Field(description="所属源 ID")
    url: str = Field(description="Sitemap URL")
    last_fetched: datetime | None = Field(default=None, description="最后抓取时间")
    fetch_status: SitemapFetchStatus = Field(
        default=SitemapFetchStatus.PENDING, description="抓取状态"
    )
    article_count: int = Field(default=0, description="文章数量")
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")


class SitemapCreate(BaseModel):
    """创建 Sitemap 请求模型"""

    source_id: int = Field(description="所属源 ID")
    url: str = Field(description="Sitemap URL")


class SitemapUpdate(BaseModel):
    """更新 Sitemap 请求模型"""

    url: str | None = Field(default=None, description="Sitemap URL")
    fetch_status: SitemapFetchStatus | None = Field(default=None, description="抓取状态")
    article_count: int | None = Field(default=None, description="文章数量")


# ============================================================================
# 待爬文章相关模型
# ============================================================================


class PendingArticle(BaseModel):
    """待爬文章模型"""

    id: int | None = Field(default=None, description="待爬文章 ID")
    source_id: int = Field(description="所属源 ID")
    sitemap_id: int | None = Field(default=None, description="来源 Sitemap ID")
    url: str = Field(description="文章 URL")
    url_hash: str = Field(description="URL 哈希（去重）")
    title: str | None = Field(default=None, description="文章标题")
    publish_time: datetime | None = Field(default=None, description="发布时间")
    status: PendingArticleStatus = Field(
        default=PendingArticleStatus.PENDING, description="状态"
    )
    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")


class PendingArticleCreate(BaseModel):
    """创建待爬文章请求模型"""

    source_id: int = Field(description="所属源 ID")
    sitemap_id: int | None = Field(default=None, description="来源 Sitemap ID")
    url: str = Field(description="文章 URL")
    title: str | None = Field(default=None, description="文章标题")
    publish_time: datetime | None = Field(default=None, description="发布时间")


class PendingArticleUpdate(BaseModel):
    """更新待爬文章请求模型"""

    status: PendingArticleStatus | None = Field(default=None, description="状态")


# 报告引用相关模型


class ReportReference(BaseModel):
    """
    报告引用模型
    存储报告中引用的文章及其上下文
    """

    id: int | None = Field(default=None, description="引用 ID")
    report_id: str = Field(description="报告 ID（UUID）")
    article_id: int = Field(description="文章 ID")
    citation_index: int = Field(description="引用序号（如 1, 2, 3...）")
    context_snippet: str | None = Field(default=None, description="AI 引用时的上下文片段")
    citation_position: int | None = Field(default=None, description="在报告中的位置")

    created_at: datetime | None = Field(default=None, description="创建时间")


class ReportMetadata(BaseModel):
    """
    报告元数据模型
    """

    id: str = Field(description="报告 ID（UUID）")
    title: str = Field(description="报告标题")
    template_id: str | None = Field(default=None, description="使用的模板 ID")
    time_range: str | None = Field(default=None, description="时间范围")
    article_count: int = Field(default=0, description="引用的文章数量")
    generated_at: datetime | None = Field(default=None, description="生成时间")

    # 报告状态
    status: str = Field(default="draft", description="报告状态：draft, published, archived")

    # 元数据
    extra_data: dict[str, Any] | None = Field(default=None, description="额外元数据")

    created_at: datetime | None = Field(default=None, description="创建时间")
    updated_at: datetime | None = Field(default=None, description="更新时间")


# SQLAlchemy Table 定义（用于构建原始 SQL）
# 这些定义用于 Repository 层构建 SQL 查询


class TableDefinition:
    """表定义辅助类"""

    @staticmethod
    def get_crawl_sources_table() -> dict[str, Any]:
        """获取 crawl_sources 表定义"""
        return {
            "name": "crawl_sources",
            "columns": [
                "id",
                "site_name",
                "base_url",
                "parser_config",
                "enabled",
                "crawl_interval",
                "created_at",
                "updated_at",
            ],
        }

    @staticmethod
    def get_articles_table() -> dict[str, Any]:
        """获取 articles 表定义"""
        return {
            "name": "articles",
            "columns": [
                "id",
                "url_hash",
                "url",
                "title",
                "content",
                "publish_time",
                "author",
                "source_id",
                "status",
                "error_message",
                "crawled_at",
                "processed_at",
                "synced_at",
                "created_at",
                "updated_at",
            ],
        }


# ============================================================================
# 任务系统模型
# ============================================================================

class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """任务类型枚举"""
    CRAWL_PENDING = "crawl_pending"  # 批量爬取待爬文章
    RETRY_FAILED = "retry_failed"  # 批量重试失败文章
    CRAWL_SOURCE = "crawl_source"  # 爬取单个源
    SEARCH_IMPORT = "search_import"  # 搜索导入
    SITEMAP_SYNC = "sitemap_sync"  # Sitemap 同步
    AUTO_SEARCH = "auto_search"  # 自动搜索


class TaskEventType(str, Enum):
    """任务事件类型枚举"""
    CREATED = "created"
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INFO = "info"


class TaskCreate(BaseModel):
    """创建任务请求"""
    task_type: TaskType
    title: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class TaskUpdate(BaseModel):
    """更新任务请求"""
    status: TaskStatus | None = None
    progress_current: int | None = None
    progress_total: int | None = None
    error_message: str | None = None
    result: dict[str, Any] | None = None


class Task(BaseModel):
    """任务模型"""
    id: int | None = None
    task_type: TaskType
    status: TaskStatus
    title: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    progress_current: int = Field(default=0)
    progress_total: int = Field(default=0)
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskEvent(BaseModel):
    """任务事件模型"""
    id: int | None = None
    task_id: int
    event_type: TaskEventType
    event_data: dict[str, Any] | None = None
    created_at: datetime | None = None


# ============================================================================
# 对话模型
# ============================================================================

class ConversationCreate(BaseModel):
    """创建对话请求"""
    title: str = "新对话"
    mode: str = "chat"  # chat, agent_web, agent_internal, agent_both
    web_search_enabled: bool = False
    internal_search_enabled: bool = False


class ConversationUpdate(BaseModel):
    """更新对话请求"""
    title: str | None = None
    mode: str | None = None
    web_search_enabled: bool | None = None
    internal_search_enabled: bool | None = None


class Conversation(BaseModel):
    """对话模型"""
    id: int | None = None
    title: str
    mode: str
    web_search_enabled: bool
    internal_search_enabled: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MessageCreate(BaseModel):
    """创建消息请求"""
    conversation_id: int
    role: str  # user, assistant, system
    content: str
    agent_state: dict[str, Any] | None = None
    search_results: dict[str, Any] | None = None


class Message(BaseModel):
    """消息模型"""
    id: int | None = None
    conversation_id: int
    role: str
    content: str
    agent_state: dict[str, Any] | None = None
    search_results: dict[str, Any] | None = None
    created_at: datetime | None = None


class ChatRequest(BaseModel):
    """聊天请求"""
    conversation_id: int | None = None  # None表示新对话
    message: str
    mode: str = "chat"
    web_search_enabled: bool = False
    internal_search_enabled: bool = False


class AgentState(BaseModel):
    """Agent状态"""
    stage: str  # generating_keywords, searching_internal, searching_web, generating_response
    keywords: list[str] = []
    internal_results: list[dict[str, Any]] = []
    web_results: list[dict[str, Any]] = []
    progress: int = 0
    total: int = 100
    message: str = ""


# ============================================================================
# 报告生成模型
# ============================================================================

class ReportStatus(str, Enum):
    """报告状态枚举"""
    DRAFT = "draft"  # 草稿
    GENERATING = "generating"  # 生成中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败

class ReportAgentStage(str, Enum):
    """报告Agent阶段枚举"""
    INITIALIZING = "initializing"  # 初始化
    FILTERING_ARTICLES = "filtering_articles"  # 筛选文章
    GENERATING_KEYWORDS = "generating_keywords"  # AI生成关键字
    CLUSTERING_ARTICLES = "clustering_articles"  # 聚类文章
    EXTRACTING_EVENTS = "extracting_events"  # 提取重点事件
    GENERATING_SECTIONS = "generating_sections"  # 生成板块
    MERGING_REPORT = "merging_report"  # 合并报告
    COMPLETED = "completed"  # 完成

class ReportCreate(BaseModel):
    """创建报告请求"""
    title: str = Field(description="报告标题")
    time_range_start: datetime = Field(description="时间范围开始")
    time_range_end: datetime = Field(description="时间范围结束")
    template_id: int | None = Field(default=None, description="模板ID")
    custom_prompt: str | None = Field(default=None, description="自定义要求")
    max_events: int = Field(default=20, description="最大事件数量")
    language: str = Field(default="zh", description="语言：zh=中文, kk=哈萨克语")

class ReportUpdate(BaseModel):
    """更新报告请求"""
    title: str | None = None
    status: ReportStatus | None = None
    content: str | None = None
    error_message: str | None = None

class Report(BaseModel):
    """报告模型"""
    id: int | None = None
    title: str = Field(description="报告标题")
    time_range_start: datetime = Field(description="时间范围开始")
    time_range_end: datetime = Field(description="时间范围结束")
    template_id: int | None = Field(default=None, description="模板ID")
    custom_prompt: str | None = Field(default=None, description="自定义要求")
    language: str = Field(default="zh", description="语言：zh=中文, kk=哈萨克语")
    max_events: int = Field(default=10, description="最大事件数量")

    # 统计信息
    total_articles: int = Field(default=0, description="总文章数")
    clustered_articles: int = Field(default=0, description="聚类后文章数")
    event_count: int = Field(default=0, description="事件数量")

    # 报告内容
    content: str | None = Field(default=None, description="报告内容（Markdown）")
    sections: list[dict[str, Any]] = Field(default_factory=list, description="报告板块")

    # 状态
    status: ReportStatus = Field(default=ReportStatus.DRAFT, description="报告状态")
    agent_stage: ReportAgentStage = Field(default=ReportAgentStage.INITIALIZING, description="Agent阶段")
    agent_progress: int = Field(default=0, description="Agent进度")
    agent_message: str = Field(default="", description="Agent消息")

    error_message: str | None = Field(default=None, description="错误信息")

    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None

class ReportTemplate(BaseModel):
    """报告模板模型"""
    id: int | None = None
    name: str = Field(description="模板名称")
    description: str | None = Field(default=None, description="模板描述")
    system_prompt: str = Field(description="系统提示词")
    section_template: list[dict[str, Any]] = Field(default_factory=list, description="板块模板")
    is_default: bool = Field(default=False, description="是否默认模板")
    created_at: datetime | None = None
    updated_at: datetime | None = None

class ReportTemplateCreate(BaseModel):
    """创建报告模板请求"""
    name: str = Field(description="模板名称")
    description: str | None = Field(default=None, description="模板描述")
    system_prompt: str = Field(description="系统提示词")
    section_template: list[dict[str, Any]] = Field(default_factory=list, description="板块模板")

class ReportEvent(BaseModel):
    """报告重点事件模型"""
    id: int | None = None
    report_id: int = Field(description="报告ID")
    event_title: str = Field(description="事件标题")
    event_summary: str = Field(description="事件摘要")
    article_count: int = Field(default=0, description="相关文章数")
    keywords: list[str] = Field(default_factory=list, description="事件关键词")
    importance_score: float = Field(default=0.0, description="重要性分数")
    created_at: datetime | None = None

class ReportSection(BaseModel):
    """报告板块模型"""
    id: int | None = None
    report_id: int = Field(description="报告ID")
    section_title: str = Field(description="板块标题")
    section_content: str = Field(description="板块内容")
    section_order: int = Field(default=0, description="板块顺序")
    event_ids: list[int] = Field(default_factory=list, description="包含的事件ID列表")
    created_at: datetime | None = None

class ReportArticle(BaseModel):
    """报告文章关联模型"""
    id: int | None = None
    report_id: int = Field(description="报告ID")
    article_id: int = Field(description="文章ID")
    event_id: int | None = Field(default=None, description="所属事件ID")
    is_representative: bool = Field(default=False, description="是否为代表文章")
    citation_index: int | None = Field(default=None, description="引用序号")
    created_at: datetime | None = None

class ReportAgentState(BaseModel):
    """报告生成Agent状态（用于流式传输）"""
    stage: ReportAgentStage
    progress: int = 0
    total: int = 100
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


# ==================== 用户模型 ====================

class UserLogin(BaseModel):
    """用户登录请求"""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class UserCreate(BaseModel):
    """创建用户请求"""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)
    role: str = "user"
    office: str | None = None


class UserUpdate(BaseModel):
    """更新用户请求"""
    password: str | None = None
    role: str | None = None
    is_active: bool | None = None
    office: str | None = None


class UserResponse(BaseModel):
    """用户响应"""
    id: int
    username: str
    role: str
    is_active: bool
    office: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    """登录响应"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
