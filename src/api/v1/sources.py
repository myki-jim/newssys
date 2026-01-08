"""
采集源管理 API
/api/v1/sources
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    APIResponse,
    BadRequestException,
    BulkOperationResponse,
    ConflictException,
    DateRangeFilter,
    NotFoundException,
    PaginatedResponse,
    ParserDebugResult,
    PaginationParams,
    SitemapNode,
    SourceFilter,
    SourceStats,
)
from src.core.models import CrawlSource, ParserConfig, SourceCreate, SourceUpdate
from src.repository.source_repository import SourceRepository


logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# 依赖注入
# ============================================================================

async def get_db() -> AsyncSession:  # type: ignore
    """获取数据库会话（占位，实际应从配置注入）"""
    from src.core.database import get_async_session
    async with get_async_session() as session:
        yield session


# ============================================================================
# CRUD 操作
# ============================================================================

@router.get("", response_model=APIResponse[PaginatedResponse[dict[str, Any]]])
async def list_sources(
    pagination: PaginationParams = Depends(),
    filter: SourceFilter = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    获取采集源列表

    支持:
    - 分页
    - 按启用状态筛选
    - 按发现策略筛选
    - 按 Robots 状态筛选
    """
    repo = SourceRepository(db)

    # 构建筛选条件
    filters: dict[str, Any] = {}
    if filter.enabled is not None:
        filters["enabled"] = filter.enabled
    if filter.discovery_method is not None:
        filters["discovery_method"] = filter.discovery_method
    if filter.robots_status is not None:
        filters["robots_status"] = filter.robots_status

    # 获取总数
    total = await repo.count(filters=filters)

    # 获取分页数据
    sources = await repo.fetch_many(
        filters=filters,
        limit=pagination.page_size,
        offset=pagination.offset,
        order_by=(
            f"created_at {pagination.sort_order}"
            if pagination.sort_by == "created_at"
            else f"site_name {pagination.sort_order}"
        ),
    )

    # 转换为字典
    items = [dict(s) for s in sources]

    paginated = PaginatedResponse.create(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    return APIResponse(success=True, data=paginated)


@router.get("/{source_id}", response_model=APIResponse[dict[str, Any]])
async def get_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单个采集源详情"""
    repo = SourceRepository(db)

    source = await repo.fetch_by_id(source_id)
    if source is None:
        raise NotFoundException(f"Source {source_id} not found")

    return APIResponse(success=True, data=dict(source))


@router.post("", response_model=APIResponse[dict[str, Any]], status_code=status.HTTP_201_CREATED)
async def create_source(
    data: SourceCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    创建采集源

    支持:
    - 单个创建
    - 批量导入（通过 bulk_create 端点）
    """
    repo = SourceRepository(db)

    # 检查是否已存在
    existing = await repo.fetch_by_base_url(data.base_url)
    if existing:
        raise ConflictException(
            message=f"Source with base_url {data.base_url} already exists",
            details={"existing_id": existing.id},
        )

    # 创建源
    source = await repo.create(data)

    logger.info(f"Created source: {source.id} - {source.site_name}")

    return APIResponse(
        success=True,
        data=dict(source),
    )


@router.post("/bulk", response_model=APIResponse[BulkOperationResponse])
async def bulk_create_sources(
    base_urls: list[str],
    default_parser_config: ParserConfig | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    批量导入采集源

    支持:
    - 批量输入 base_url 列表
    - 自动去重
    - 自动识别站点名称
    """
    repo = SourceRepository(db)

    success_count = 0
    failed_count = 0
    errors = []

    for url in base_urls:
        try:
            # 规范化 URL
            url = url.strip()
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            # 检查是否已存在
            existing = await repo.fetch_by_base_url(url)
            if existing:
                errors.append({
                    "url": url,
                    "error": "Already exists",
                    "existing_id": existing.id,
                })
                failed_count += 1
                continue

            # 提取站点名称
            from urllib.parse import urlparse
            parsed = urlparse(url)
            site_name = parsed.netloc.replace("www.", "")

            # 创建源
            data = SourceCreate(
                site_name=site_name,
                base_url=url,
                parser_config=default_parser_config or ParserConfig(
                    title_selector="h1",
                    content_selector="article, main",
                ),
            )

            await repo.create(data)
            success_count += 1

        except Exception as e:
            logger.error(f"Failed to create source from URL {url}: {e}")
            errors.append({
                "url": url,
                "error": str(e),
            })
            failed_count += 1

    logger.info(f"Bulk create sources: {success_count} succeeded, {failed_count} failed")

    return APIResponse(
        success=True,
        data=BulkOperationResponse(
            success_count=success_count,
            failed_count=failed_count,
            errors=errors,
        ),
    )


@router.put("/{source_id}", response_model=APIResponse[dict[str, Any]])
async def update_source(
    source_id: int,
    data: SourceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    更新采集源配置

    注意：启用源前必须先配置 Sitemap
    没有有效 Sitemap 的源无法启用
    """
    repo = SourceRepository(db)

    source = await repo.fetch_by_id(source_id)
    if source is None:
        raise NotFoundException(f"Source {source_id} not found")

    # 验证：如果要启用源，必须有有效的 Sitemap
    if data.enabled is True:
        from src.repository.sitemap_repository import SitemapRepository
        sitemap_repo = SitemapRepository(db)

        sitemaps = await sitemap_repo.get_by_source(source_id)
        if not sitemaps:
            raise BadRequestException(
                message="Cannot enable source: No sitemap configured. "
                       "Please add a sitemap first.",
                details={"source_id": source_id, "sitemaps_count": 0},
            )

    updated = await repo.update(source_id, data)

    return APIResponse(success=True, data=dict(updated))


@router.delete("/{source_id}", response_model=APIResponse[dict[str, Any]])
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除采集源（级联删除相关文章）"""
    repo = SourceRepository(db)

    source = await repo.fetch_by_id(source_id)
    if source is None:
        raise NotFoundException(f"Source {source_id} not found")

    await repo.delete(source_id)

    logger.info(f"Deleted source: {source_id}")

    return APIResponse(success=True, data={"deleted_id": source_id})


# ============================================================================
# 配置调试
# ============================================================================

@router.post("/debug/parser", response_model=APIResponse[ParserDebugResult])
async def debug_parser(
    url: str,
    config: ParserConfig,
    db: AsyncSession = Depends(get_db),
):
    """
    实时调试解析器配置

    返回:
    - 提取的标题
    - 提取的内容 (Markdown 格式)
    - 提取的时间
    - 提取的作者
    """
    import time

    from src.services.universal_scraper import UniversalScraper
    from src.services.time_extractor import TimeExtractor

    start_time = time.time()

    try:
        # 使用 UniversalScraper 抓取
        scraper = UniversalScraper()
        article = await scraper.scrape(
            url=url,
            parser_config=config,
            source_id=0,  # 调试模式，不关联具体源
        )

        # 使用 TimeExtractor 提取时间
        time_extractor = TimeExtractor()
        if article.publish_time is None and article.content:
            article.publish_time = time_extractor.extract_time(
                html="",  # 已经提取过了
                url=url,
                content=article.content,
                title=article.title,
            )

        extraction_time = int((time.time() - start_time) * 1000)

        return APIResponse(
            success=True,
            data=ParserDebugResult(
                url=url,
                title=article.title,
                content=article.content,
                publish_time=article.publish_time,
                author=article.author,
                raw_html_length=len(article.content) if article.content else 0,
                extraction_time_ms=extraction_time,
            ),
        )

    except Exception as e:
        logger.error(f"Parser debug failed for {url}: {e}")

        extraction_time = int((time.time() - start_time) * 1000)

        return APIResponse(
            success=False,
            data=ParserDebugResult(
                url=url,
                error=str(e),
                extraction_time_ms=extraction_time,
            ),
        )


# ============================================================================
# Sitemap 操作
# ============================================================================

@router.get("/{source_id}/sitemap", response_model=APIResponse[list[dict[str, Any]]])
async def get_source_sitemaps(
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    获取源的 Sitemap 列表

    返回该源关联的所有 Sitemap
    """
    from src.repository.sitemap_repository import SitemapRepository

    repo = SourceRepository(db)
    sitemap_repo = SitemapRepository(db)

    # 检查源是否存在
    source = await repo.fetch_by_id(source_id)
    if source is None:
        raise NotFoundException(f"Source {source_id} not found")

    # 获取源的所有 sitemap
    sitemaps = await sitemap_repo.get_by_source(source_id)

    return APIResponse(success=True, data=[dict(s) for s in sitemaps])


@router.post("/{source_id}/sitemap/discover", response_model=APIResponse[dict[str, Any]])
async def discover_sitemaps(
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    从 robots.txt 发现并存储 Sitemap

    自动解析 robots.txt，提取所有 Sitemap URL 并存储到数据库
    """
    from src.services.sitemap_service import SitemapService

    repo = SourceRepository(db)

    # 检查源是否存在
    source = await repo.fetch_by_id(source_id)
    if source is None:
        raise NotFoundException(f"Source {source_id} not found")

    service = SitemapService(db)
    try:
        sitemaps = await service.fetch_robots_sitemaps(source_id)

        return APIResponse(
            success=True,
            data={
                "source_id": source_id,
                "sitemaps_found": len(sitemaps),
                "sitemaps": [dict(s) for s in sitemaps],
            },
        )
    finally:
        await service.close()


@router.post("/{source_id}/sitemap/sync", response_model=APIResponse[dict[str, Any]])
async def sync_sitemap_articles(
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    同步 Sitemap 文章到待爬表

    完整流程：
    1. 从 robots.txt 获取 Sitemap（如果需要）
    2. 递归解析所有 Sitemap
    3. 提取文章链接到待爬表
    """
    from src.services.sitemap_service import SitemapService

    repo = SourceRepository(db)

    # 检查源是否存在
    source = await repo.fetch_by_id(source_id)
    if source is None:
        raise NotFoundException(f"Source {source_id} not found")

    service = SitemapService(db)
    try:
        result = await service.sync_source_sitemaps(source_id)

        return APIResponse(success=True, data=result)
    finally:
        await service.close()


# ============================================================================
# Robots.txt 操作
# ============================================================================

@router.get("/{source_id}/robots", response_model=APIResponse[dict[str, Any]])
async def get_robots_status(
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取 Robots.txt 状态"""
    repo = SourceRepository(db)

    source = await repo.fetch_by_id(source_id)
    if source is None:
        raise NotFoundException(f"Source {source_id} not found")

    return APIResponse(
        success=True,
        data={
            "source_id": source_id,
            "robots_status": source.robots_status.value,
            "crawl_delay": source.crawl_delay,
            "robots_fetched_at": source.robots_fetched_at.isoformat() if source.robots_fetched_at else None,
        },
    )


@router.post("/{source_id}/robots/fetch", response_model=APIResponse[dict[str, Any]])
async def fetch_robots(
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    """手动获取 Robots.txt"""
    repo = SourceRepository(db)

    source = await repo.fetch_by_id(source_id)
    if source is None:
        raise NotFoundException(f"Source {source_id} not found")

    from src.services.robots_handler import RobotsHandler

    handler = RobotsHandler()
    robots_info = await handler.fetch_and_parse(source.base_url + "/robots.txt")

    # 更新源配置
    await repo.update(source_id, SourceUpdate(
        robots_status=robots_info["status"],
        crawl_delay=robots_info.get("crawl_delay"),
        robots_fetched_at=datetime.now(),
    ))

    return APIResponse(
        success=True,
        data={
            "source_id": source_id,
            "robots_status": robots_info["status"].value,
            "crawl_delay": robots_info.get("crawl_delay"),
            "allowed_paths": robots_info.get("allowed_paths", []),
            "disallowed_paths": robots_info.get("disallowed_paths", []),
        },
    )


# ============================================================================
# 统计数据
# ============================================================================

@router.get("/stats/all", response_model=APIResponse[list[SourceStats]])
async def get_sources_stats(
    days: int = Query(default=30, ge=1, le=365, description="统计天数"),
    db: AsyncSession = Depends(get_db),
):
    """获取所有源的统计数据"""
    repo = SourceRepository(db)

    from datetime import timedelta
    start_date = datetime.now() - timedelta(days=days)

    stats = await repo.get_stats(start_date=start_date)

    return APIResponse(success=True, data=stats)


@router.post("/{source_id}/crawl", response_model=APIResponse[dict[str, Any]])
async def trigger_crawl(
    source_id: int,
    force: bool = Query(default=False, description="强制抓取（忽略间隔限制）"),
    db: AsyncSession = Depends(get_db),
):
    """
    手动触发抓取任务

    队列化处理，立即返回任务 ID
    """
    repo = SourceRepository(db)

    source = await repo.fetch_by_id(source_id)
    if source is None:
        raise NotFoundException(f"Source {source_id} not found")

    if not source.enabled:
        raise BadRequestException(f"Source {source_id} is disabled")

    # TODO: 队列化处理
    # from src.services.collector import NewsCollector
    # collector = NewsCollector()
    # task_id = await collector.crawl_source(source_id, force=force)

    return APIResponse(
        success=True,
        data={
            "source_id": source_id,
            "task_id": f"crawl_{source_id}_{datetime.now().timestamp()}",
            "status": "queued",
        },
    )
