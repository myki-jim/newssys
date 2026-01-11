"""
API 请求/响应 Schema
统一的 API 数据结构
"""

from datetime import datetime
from typing import Any, Generic, TypeVar

from fastapi import status
from pydantic import BaseModel, Field


# ============================================================================
# 通用响应结构
# ============================================================================

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""
    success: bool = Field(description="请求是否成功")
    data: T | None = Field(default=None, description="响应数据")
    error: "APIError | None" = Field(default=None, description="错误信息")

    class Config:
        # 允许泛型
        arbitrary_types_allowed = True


class APIError(BaseModel):
    """错误信息"""
    code: str = Field(description="错误代码")
    message: str = Field(description="错误消息")
    details: dict[str, Any] | None = Field(default=None, description="详细错误信息")


# ============================================================================
# 分页模型
# ============================================================================

class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    sort_by: str | None = Field(default=None, description="排序字段")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="排序方向")

    @property
    def offset(self) -> int:
        """计算偏移量"""
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: list[T] = Field(description="数据列表")
    total: int = Field(description="总数量")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    total_pages: int = Field(description="总页数")

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "PaginatedResponse[T]":
        """创建分页响应"""
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


# ============================================================================
# 筛选模型
# ============================================================================

class DateRangeFilter(BaseModel):
    """日期范围筛选"""
    start: datetime | None = Field(default=None, description="开始日期")
    end: datetime | None = Field(default=None, description="结束日期")


class ArticleFilter(BaseModel):
    """文章筛选条件"""
    source_ids: list[int] | None = Field(default=None, description="源 ID 列表")
    source_search: str | None = Field(default=None, description="源名称搜索")
    status: str | None = Field(default=None, description="文章状态")
    fetch_status: str | None = Field(default=None, description="抓取状态")
    keyword: str | None = Field(default=None, description="关键词搜索")
    url_hash: str | None = Field(default=None, description="URL 哈希")
    date_range: DateRangeFilter | None = Field(default=None, description="采集时间范围")
    publish_time_range: DateRangeFilter | None = Field(default=None, description="发布时间范围")
    min_score: float | None = Field(default=None, description="最低影响力分数")


class SourceFilter(BaseModel):
    """源筛选条件"""
    enabled: bool | None = Field(default=None, description="是否启用")
    discovery_method: str | None = Field(default=None, description="发现策略")
    robots_status: str | None = Field(default=None, description="Robots 状态")


# ============================================================================
# 操作响应
# ============================================================================

class BulkOperationResponse(BaseModel):
    """批量操作响应"""
    success_count: int = Field(description="成功数量")
    failed_count: int = Field(description="失败数量")
    errors: list[dict[str, Any]] = Field(default_factory=list, description="错误详情")


class BulkOperationItem(BaseModel):
    """批量操作项"""
    id: int = Field(description="项 ID")
    action: str = Field(description="操作类型")


# ============================================================================
# 调试/预览响应
# ============================================================================

class ParserDebugResult(BaseModel):
    """解析器调试结果"""
    url: str = Field(description="测试 URL")
    title: str | None = Field(default=None, description="提取的标题")
    content: str | None = Field(default=None, description="提取的内容")
    publish_time: datetime | None = Field(default=None, description="提取的时间")
    author: str | None = Field(default=None, description="提取的作者")
    error: str | None = Field(default=None, description="错误信息")
    raw_html_length: int | None = Field(default=None, description="原始 HTML 长度")
    extraction_time_ms: int | None = Field(default=None, description="提取耗时（毫秒）")


class SitemapNode(BaseModel):
    """Sitemap 树节点"""
    url: str = Field(description="URL")
    lastmod: datetime | None = Field(default=None, description="最后修改时间")
    children: list["SitemapNode"] = Field(default_factory=list, description="子节点")
    depth: int = Field(default=0, description="深度")

    class Config:
        # 支持递归类型
        arbitrary_types_allowed = True


# ============================================================================
# SSE 事件
# ============================================================================

class SSEEvent(BaseModel):
    """Server-Sent Events 事件"""
    event: str = Field(description="事件类型")
    data: dict[str, Any] = Field(description="事件数据")
    id: str | None = Field(default=None, description="事件 ID")


# ============================================================================
# 报告相关
# ============================================================================

class ReportGenerateRequest(BaseModel):
    """报告生成请求"""
    title: str = Field(description="报告标题")
    template_id: str | None = Field(default=None, description="模板 ID")
    time_range: str = Field(default="week", description="时间范围")
    source_ids: list[int] | None = Field(default=None, description="源 ID 列表")
    keywords: list[str] | None = Field(default=None, description="关键词列表")
    max_articles: int = Field(default=20, ge=1, le=100, description="最大文章数")
    enable_search: bool = Field(default=False, description="是否启用联网搜索")
    search_query: str | None = Field(default=None, description="联网搜索查询")
    context_text: str | None = Field(default=None, description="额外上下文")


class ReportReferenceDetail(BaseModel):
    """报告引用详情"""
    id: int = Field(description="引用 ID")
    report_id: str = Field(description="报告 ID")
    article_id: int = Field(description="文章 ID")
    citation_index: int = Field(description="引用序号")
    context_snippet: str | None = Field(default=None, description="上下文片段")

    # 文章详情
    article_title: str = Field(description="文章标题")
    article_url: str = Field(description="文章 URL")
    article_content: str | None = Field(default=None, description="文章内容")
    article_source: str | None = Field(default=None, description="文章来源")
    article_publish_time: datetime | None = Field(default=None, description="发布时间")


class ReportResponse(BaseModel):
    """报告响应"""
    id: str = Field(description="报告 ID")
    title: str = Field(description="报告标题")
    template_id: str | None = Field(default=None, description="模板 ID")
    time_range: str | None = Field(default=None, description="时间范围")
    article_count: int = Field(description="引用文章数")
    content: str | None = Field(default=None, description="报告内容 (Markdown)")
    status: str = Field(description="报告状态")
    generated_at: datetime | None = Field(default=None, description="生成时间")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


# ============================================================================
# 统计数据
# ============================================================================

class DashboardStats(BaseModel):
    """仪表盘统计数据"""
    total_sources: int = Field(description="总源数")
    active_sources: int = Field(description="活跃源数")
    total_articles: int = Field(description="总文章数")
    today_articles: int = Field(description="今日新增文章")
    failed_articles: int = Field(description="失败文章数")
    total_reports: int = Field(description="总报告数")
    avg_processing_time: float | None = Field(default=None, description="平均处理时间（秒）")
    storage_used_mb: float | None = Field(default=None, description="存储使用（MB）")


class SourceStats(BaseModel):
    """源统计"""
    source_id: int = Field(description="源 ID")
    site_name: str = Field(description="站点名称")
    total_articles: int = Field(description="总文章数")
    success_count: int = Field(description="成功次数")
    failure_count: int = Field(description="失败次数")
    success_rate: float = Field(description="成功率")
    last_crawled_at: datetime | None = Field(default=None, description="最后爬取时间")


class SearchSaveRequest(BaseModel):
    """搜索结果保存请求"""
    url: str = Field(description="文章 URL")
    title: str = Field(description="文章标题")
    source_id: int | None = Field(default=None, description="源 ID（可选，自动推断）")


class BulkDeleteRequest(BaseModel):
    """批量删除请求"""
    article_ids: list[int] = Field(description="要删除的文章 ID 列表")


# ============================================================================
# 异常类
# ============================================================================

class APIException(Exception):
    """API 异常基类"""

    def __init__(
        self,
        message: str,
        code: str = "API_ERROR",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict | None = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details


class NotFoundException(APIException):
    """资源未找到 (404)"""

    def __init__(self, message: str = "Resource not found", details: dict | None = None):
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class BadRequestException(APIException):
    """错误请求 (400)"""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(
            message=message,
            code="BAD_REQUEST",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class UnprocessableEntityException(APIException):
    """无法处理的实体 (422)"""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(
            message=message,
            code="UNPROCESSABLE_ENTITY",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class ConflictException(APIException):
    """冲突 (409)"""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class InternalServerException(APIException):
    """服务器内部错误 (500)"""

    def __init__(self, message: str = "Internal server error", details: dict | None = None):
        super().__init__(
            message=message,
            code="INTERNAL_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


# ============================================================================
# 定时任务相关 Schema
# ============================================================================


class ScheduleCreate(BaseModel):
    """创建定时任务请求"""
    name: str = Field(..., description="任务名称")
    description: str | None = Field(None, description="任务描述")
    schedule_type: str = Field(..., description="任务类型: sitemap_crawl, article_crawl, keyword_search")
    interval_minutes: int = Field(60, description="执行间隔（分钟）")
    max_executions: int | None = Field(None, description="最大执行次数，None表示无限")
    config: dict[str, Any] | None = Field(None, description="任务配置")


class ScheduleUpdate(BaseModel):
    """更新定时任务请求"""
    name: str | None = None
    description: str | None = None
    status: str | None = None  # active, paused, disabled
    interval_minutes: int | None = None
    max_executions: int | None = None
    config: dict[str, Any] | None = None


class ScheduleResponse(BaseModel):
    """定时任务响应"""
    id: int
    name: str
    description: str | None
    schedule_type: str
    status: str
    interval_minutes: int
    max_executions: int | None
    execution_count: int
    config: dict[str, Any] | None
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_status: str | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


# ============================================================================
# 关键词相关 Schema
# ============================================================================


class KeywordCreate(BaseModel):
    """创建关键词请求"""
    keyword: str = Field(..., description="关键词")
    description: str | None = Field(None, description="描述")
    time_range: str = Field("w", description="时间范围: d, w, m, y")
    max_results: int = Field(10, description="最大结果数")
    region: str = Field("us-en", description="地区")
    is_active: bool = Field(True, description="是否激活")


class KeywordUpdate(BaseModel):
    """更新关键词请求"""
    keyword: str | None = None
    description: str | None = None
    time_range: str | None = None
    max_results: int | None = None
    region: str | None = None
    is_active: bool | None = None


class KeywordResponse(BaseModel):
    """关键词响应"""
    id: int
    keyword: str
    description: str | None
    time_range: str
    max_results: int
    region: str
    is_active: bool
    search_count: int
    last_searched_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ScheduleExecuteRequest(BaseModel):
    """执行定时任务请求"""
    schedule_id: int = Field(..., description="任务ID")


class ScheduleExecuteResponse(BaseModel):
    """执行定时任务响应"""
    task_id: int
    schedule_id: int
    status: str
