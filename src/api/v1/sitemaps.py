"""
Sitemap API
/api/v1/sitemaps

管理 Sitemap 和待爬文章
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import APIResponse, BadRequestException, NotFoundException
from src.core.models import (
    PendingArticleCreate,
    PendingArticleStatus,
    SitemapCreate,
    SitemapFetchStatus,
    SitemapUpdate,
)
from src.repository.pending_article_repository import PendingArticleRepository
from src.repository.sitemap_repository import SitemapRepository
from src.services.sitemap_service import SitemapService


logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# 依赖注入
# ============================================================================

async def get_db() -> AsyncSession:  # type: ignore
    """获取数据库会话"""
    from src.core.database import get_async_session
    async with get_async_session() as session:
        yield session


# ============================================================================
# Sitemap 管理
# ============================================================================

@router.get("", response_model=APIResponse[list[dict[str, Any]]])
async def list_sitemaps(
    source_id: int | None = Query(default=None, description="源 ID 筛选"),
    db: AsyncSession = Depends(get_db),
):
    """获取 Sitemap 列表"""
    repo = SitemapRepository(db)

    if source_id is not None:
        sitemaps = await repo.get_by_source(source_id)
    else:
        # 获取所有 sitemap
        sitemaps = await repo.fetch_all(
            "SELECT * FROM sitemaps ORDER BY created_at DESC LIMIT 1000"
        )

    return APIResponse(success=True, data=[dict(s) for s in sitemaps])


@router.post("", response_model=APIResponse[dict[str, Any]])
async def create_sitemap(
    sitemap: SitemapCreate,
    db: AsyncSession = Depends(get_db),
):
    """手动创建 Sitemap"""
    repo = SitemapRepository(db)

    # 检查 URL 是否已存在
    existing = await repo.get_by_url(sitemap.url)
    if existing:
        return APIResponse(
            success=False,
            data={"error": "Sitemap URL already exists"},
        )

    sitemap_id = await repo.create(sitemap)

    return APIResponse(
        success=True,
        data={"id": sitemap_id, "url": sitemap.url, "source_id": sitemap.source_id},
    )


# ============================================================================
# 待爬文章管理（放在 /{sitemap_id} 之前避免路由冲突）
# ============================================================================

@router.get("/pending", response_model=APIResponse[list[dict[str, Any]]])
async def list_pending_articles(
    source_id: int | None = Query(default=None, description="源 ID 筛选"),
    sitemap_id: int | None = Query(default=None, description="Sitemap ID 筛选"),
    status: str | None = Query(default=None, description="状态筛选"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """获取待爬文章列表"""
    repo = PendingArticleRepository(db)

    # 转换状态字符串为枚举
    status_enum = None
    if status:
        try:
            status_enum = PendingArticleStatus(status)
        except ValueError:
            pass  # 无效状态，忽略筛选

    if sitemap_id is not None:
        articles = await repo.get_by_sitemap(sitemap_id, status=status_enum)
    elif source_id is not None:
        articles = await repo.get_by_source(source_id, status=status_enum, limit=limit, offset=offset)
    else:
        # 获取所有待爬文章，按发布时间倒序（最新的优先），没有发布时间的排在最后（自动过滤低质量）
        articles = await repo.fetch_all(
            f"SELECT * FROM pending_articles WHERE status != 'low_quality' ORDER BY publish_time DESC NULLS LAST, created_at DESC LIMIT {limit} OFFSET {offset}"
        )

    return APIResponse(success=True, data=[dict(a) for a in articles])


@router.get("/pending/stats", response_model=APIResponse[dict[str, Any]])
async def get_pending_stats(
    source_id: int | None = Query(default=None, description="源 ID 筛选"),
    db: AsyncSession = Depends(get_db),
):
    """获取待爬文章统计"""
    repo = PendingArticleRepository(db)

    stats = {
        "total": await repo.count_by_status(source_id=source_id),
        "pending": await repo.count_by_status(source_id=source_id, status=PendingArticleStatus.PENDING),
        "crawling": await repo.count_by_status(source_id=source_id, status=PendingArticleStatus.CRAWLING),
        "completed": await repo.count_by_status(source_id=source_id, status=PendingArticleStatus.COMPLETED),
        "failed": await repo.count_by_status(source_id=source_id, status=PendingArticleStatus.FAILED),
        "abandoned": await repo.count_by_status(source_id=source_id, status=PendingArticleStatus.ABANDONED),
    }

    return APIResponse(success=True, data=stats)


@router.delete("/pending/{article_id}", response_model=APIResponse[dict[str, Any]])
async def delete_pending_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除待爬文章"""
    repo = PendingArticleRepository(db)

    article = await repo.get_by_id(article_id)
    if not article:
        raise NotFoundException(f"Pending article {article_id} not found")

    await repo.delete_by_id(article_id)

    return APIResponse(success=True, data={"deleted_id": article_id})


@router.post("/pending/crawl/{source_id}", response_model=APIResponse[dict[str, Any]])
async def crawl_pending_articles(
    source_id: int,
    limit: int = Query(default=10, ge=1, le=100, description="爬取数量限制"),
    db: AsyncSession = Depends(get_db),
):
    """
    爬取待爬文章

    从待爬表获取文章并执行爬取，类似搜索入库流程

    完整流程：
    1. 获取待爬文章
    2. 使用 UniversalScraper 抓取内容
    3. 保存到 articles 表
    4. 更新 pending 状态
    """
    import asyncio
    import hashlib

    from src.repository.article_repository import ArticleRepository
    from src.repository.source_repository import SourceRepository
    from src.services.universal_scraper import UniversalScraper
    from src.core.models import ArticleCreate, ArticleStatus

    pending_repo = PendingArticleRepository(db)
    article_repo = ArticleRepository(db)
    source_repo = SourceRepository(db)

    # 获取源信息
    source = await source_repo.fetch_by_id(source_id)
    if not source:
        raise NotFoundException(f"Source {source_id} not found")

    # 解析 parser_config
    parser_config = source.get("parser_config")
    if isinstance(parser_config, str):
        from src.core.models import ParserConfig
        parser_config = ParserConfig.model_validate_json(parser_config)

    # 获取待爬文章
    articles = await pending_repo.get_by_source(
        source_id,
        status=PendingArticleStatus.PENDING,
        limit=limit,
    )

    if not articles:
        return APIResponse(
            success=True,
            data={"crawled": 0, "failed": 0, "skipped": 0, "message": "No pending articles"},
        )

    crawled_count = 0
    failed_count = 0
    skipped_count = 0

    for pending_article in articles:
        try:
            article_id = pending_article["id"]
            url = pending_article["url"]

            # 检查 URL 是否已存在于 articles 表
            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
            existing = await article_repo.get_by_url_hash(url_hash)

            if existing:
                # 已存在，标记为已完成
                await pending_repo.update_status(article_id, PendingArticleStatus.COMPLETED)
                skipped_count += 1
                logger.info(f"Article already exists: {url}")
                continue

            # 更新状态为爬取中
            await pending_repo.update_status(article_id, PendingArticleStatus.CRAWLING)

            # 使用 UniversalScraper 抓取内容
            async with UniversalScraper() as scraper:
                article = await scraper.scrape(
                    url=url,
                    parser_config=parser_config,
                    source_id=source_id,
                )

            if article.error:
                # 爬取失败
                await pending_repo.update_status(article_id, PendingArticleStatus.FAILED)
                failed_count += 1
                logger.error(f"Failed to crawl {url}: {article.error}")
                continue

            # 验证内容
            if not article.content or len(article.content) < 50:
                await pending_repo.update_status(article_id, PendingArticleStatus.FAILED)
                failed_count += 1
                logger.error(f"Content too short for {url}")
                continue

            # 创建文章
            create_data = ArticleCreate(
                url=url,
                title=article.title or pending_article.get("title") or "Untitled",
                content=article.content,
                publish_time=article.publish_time or pending_article.get("publish_time"),
                author=article.author,
                source_id=source_id,
            )

            new_article_id = await article_repo.create(create_data)

            # 更新待爬文章状态为已完成
            await pending_repo.update_status(article_id, PendingArticleStatus.COMPLETED)

            crawled_count += 1
            logger.info(f"Successfully crawled and saved article {new_article_id}: {url}")

        except Exception as e:
            # 爬取失败
            await pending_repo.update_status(pending_article["id"], PendingArticleStatus.FAILED)
            failed_count += 1
            logger.error(f"Error crawling article {pending_article['url']}: {e}", exc_info=True)

        # 添加延迟避免被封禁
        await asyncio.sleep(1)

    return APIResponse(
        success=True,
        data={
            "crawled": crawled_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "total": len(articles),
            "message": f"Crawled {crawled_count}, failed {failed_count}, skipped {skipped_count}",
        },
    )


@router.post("/pending/crawl-single/{article_id}", response_model=APIResponse[dict[str, Any]])
async def crawl_single_pending_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    爬取单个待爬文章

    类似搜索入库流程，但针对单个待爬文章
    """
    import hashlib

    from src.repository.article_repository import ArticleRepository
    from src.repository.source_repository import SourceRepository
    from src.services.universal_scraper import UniversalScraper
    from src.core.models import ArticleCreate, ArticleStatus, ParserConfig

    pending_repo = PendingArticleRepository(db)
    article_repo = ArticleRepository(db)
    source_repo = SourceRepository(db)

    # 获取待爬文章
    pending_article = await pending_repo.get_by_id(article_id)
    if not pending_article:
        raise NotFoundException(f"Pending article {article_id} not found")

    url = pending_article["url"]
    source_id = pending_article["source_id"]

    # 检查 URL 是否已存在
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
    existing = await article_repo.get_by_url_hash(url_hash)

    if existing:
        # 已存在，标记为已完成
        await pending_repo.update_status(article_id, PendingArticleStatus.COMPLETED)
        return APIResponse(
            success=True,
            data={
                "article": dict(existing),
                "status": "already_exists",
                "message": "Article already exists in database",
            },
        )

    # 获取源信息
    source = await source_repo.fetch_by_id(source_id)
    if not source:
        raise NotFoundException(f"Source {source_id} not found")

    # 解析 parser_config
    parser_config = source.get("parser_config")
    if isinstance(parser_config, str):
        parser_config = ParserConfig.model_validate_json(parser_config)

    # 更新状态为爬取中
    await pending_repo.update_status(article_id, PendingArticleStatus.CRAWLING)

    try:
        # 使用 UniversalScraper 抓取内容
        async with UniversalScraper() as scraper:
            article = await scraper.scrape(
                url=url,
                parser_config=parser_config,
                source_id=source_id,
            )

        if article.error:
            await pending_repo.update_status(article_id, PendingArticleStatus.FAILED)
            raise BadRequestException(f"Failed to crawl article: {article.error}")

        # 验证内容
        if not article.content or len(article.content) < 50:
            await pending_repo.update_status(article_id, PendingArticleStatus.FAILED)
            raise BadRequestException(f"Content too short: {len(article.content) if article.content else 0} characters")

        # 创建文章
        create_data = ArticleCreate(
            url=url,
            title=article.title or pending_article.get("title") or "Untitled",
            content=article.content,
            publish_time=article.publish_time or pending_article.get("publish_time"),
            author=article.author,
            source_id=source_id,
        )

        new_article_id = await article_repo.create(create_data)
        article_data = await article_repo.get_by_id(new_article_id)

        # 更新待爬文章状态为已完成
        await pending_repo.update_status(article_id, PendingArticleStatus.COMPLETED)

        logger.info(f"Successfully crawled single article {new_article_id}: {url}")

        return APIResponse(
            success=True,
            data={
                "article": dict(article_data),
                "status": "created",
                "message": "Article successfully crawled and saved",
            },
        )

    except Exception as e:
        await pending_repo.update_status(article_id, PendingArticleStatus.FAILED)
        logger.error(f"Error crawling article {url}: {e}", exc_info=True)
        raise


@router.get("/pending/crawl-all")
async def crawl_all_pending_articles(
    limit_per_source: int = Query(default=10, ge=1, le=100, description="每个源爬取数量限制"),
    db: AsyncSession = Depends(get_db),
):
    """
    全局批量爬取所有源的待爬文章 (SSE 流式返回)

    自动识别所有有待爬文章的源，然后依次爬取
    实时返回爬取进度和结果
    """
    from src.repository.source_repository import SourceRepository
    from src.repository.article_repository import ArticleRepository
    from src.services.universal_scraper import UniversalScraper
    from src.core.models import ArticleCreate, ParserConfig
    import hashlib

    async def event_stream():
        source_repo = SourceRepository(db)
        pending_repo = PendingArticleRepository(db)
        article_repo = ArticleRepository(db)

        # 获取所有源
        sources = await source_repo.fetch_all(
            "SELECT DISTINCT s.* FROM crawl_sources s "
            "INNER JOIN pending_articles p ON s.id = p.source_id "
            "WHERE p.status = 'pending' "
            "ORDER BY s.site_name"
        )

        if not sources:
            yield f"event: start\ndata: {json.dumps({'sources_count': 0, 'message': 'No sources with pending articles found'})}\n\n"
            yield f"event: complete\ndata: {json.dumps({'crawled': 0, 'failed': 0, 'skipped': 0})}\n\n"
            return

        total_crawled = 0
        total_failed = 0
        total_skipped = 0

        # 发送开始事件
        yield f"event: start\ndata: {json.dumps({'sources_count': len(sources), 'message': f'Starting crawl for {len(sources)} sources'})}\n\n"

        for idx, source in enumerate(sources):
            source_id = source["id"]
            source_name = source["site_name"]

            try:
                parser_config = source.get("parser_config")
                if isinstance(parser_config, str):
                    parser_config = ParserConfig.model_validate_json(parser_config)

                articles = await pending_repo.get_by_source(
                    source_id,
                    status=PendingArticleStatus.PENDING,
                    limit=limit_per_source,
                )

                if not articles:
                    continue

                # 发送源开始事件
                yield f"event: source_start\ndata: {json.dumps({'source_id': source_id, 'source_name': source_name, 'articles_count': len(articles), 'source_index': idx + 1})}\n\n"

                crawled_count = 0
                failed_count = 0
                skipped_count = 0

                for article_idx, pending_article in enumerate(articles):
                    try:
                        article_id = pending_article["id"]
                        url = pending_article["url"]

                        # 检查 URL 是否已存在
                        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
                        existing = await article_repo.get_by_url_hash(url_hash)

                        if existing:
                            await pending_repo.update_status(article_id, PendingArticleStatus.COMPLETED)
                            skipped_count += 1
                            yield f"event: article_skipped\ndata: {json.dumps({'url': url, 'reason': 'already_exists'})}\n\n"
                            continue

                        await pending_repo.update_status(article_id, PendingArticleStatus.CRAWLING)

                        async with UniversalScraper() as scraper:
                            article = await scraper.scrape(
                                url=url,
                                parser_config=parser_config,
                                source_id=source_id,
                            )

                        if article.error:
                            await pending_repo.update_status(article_id, PendingArticleStatus.FAILED)
                            failed_count += 1
                            yield f"event: article_failed\ndata: {json.dumps({'url': url, 'error': article.error})}\n\n"
                            continue

                        if not article.content or len(article.content) < 50:
                            await pending_repo.update_status(article_id, PendingArticleStatus.FAILED)
                            failed_count += 1
                            yield f"event: article_failed\ndata: {json.dumps({'url': url, 'error': 'Content too short'})}\n\n"
                            continue

                        create_data = ArticleCreate(
                            url=url,
                            title=article.title or pending_article.get("title") or "Untitled",
                            content=article.content,
                            publish_time=article.publish_time or pending_article.get("publish_time"),
                            author=article.author,
                            source_id=source_id,
                        )

                        new_article_id = await article_repo.create(create_data)
                        await pending_repo.update_status(article_id, PendingArticleStatus.COMPLETED)

                        crawled_count += 1
                        # 发送单个文章成功事件
                        yield f"event: article_success\ndata: {json.dumps({'article_id': new_article_id, 'url': url, 'title': article.title})}\n\n"

                    except Exception as e:
                        await pending_repo.update_status(pending_article["id"], PendingArticleStatus.FAILED)
                        failed_count += 1
                        yield f"event: article_failed\ndata: {json.dumps({'url': pending_article['url'], 'error': str(e)})}\n\n"

                    await asyncio.sleep(1)

                total_crawled += crawled_count
                total_failed += failed_count
                total_skipped += skipped_count

                # 发送源完成事件
                yield f"event: source_complete\ndata: {json.dumps({'source_id': source_id, 'source_name': source_name, 'crawled': crawled_count, 'failed': failed_count, 'skipped': skipped_count})}\n\n"

            except Exception as e:
                logger.error(f"Error processing source {source_name}: {e}", exc_info=True)
                continue

        # 发送完成事件
        yield f"event: complete\ndata: {json.dumps({'crawled': total_crawled, 'failed': total_failed, 'skipped': total_skipped, 'total': total_crawled + total_failed + total_skipped})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/pending/retry-failed")
async def retry_failed_articles(
    source_id: int | None = Query(default=None, description="源 ID（不指定则重试所有源的失败文章）"),
    limit: int = Query(default=10, ge=1, le=100, description="每个源重试数量限制"),
    db: AsyncSession = Depends(get_db),
):
    """
    批量重试失败的待爬文章 (SSE 流式返回)

    将失败的文章状态重置为 pending，然后重新爬取
    实时返回重试进度和结果
    """
    from src.repository.source_repository import SourceRepository
    from src.repository.article_repository import ArticleRepository
    from src.services.universal_scraper import UniversalScraper
    from src.core.models import ArticleCreate, ParserConfig
    import hashlib

    async def event_stream():
        source_repo = SourceRepository(db)
        pending_repo = PendingArticleRepository(db)
        article_repo = ArticleRepository(db)

        # 获取源列表
        if source_id is not None:
            source = await source_repo.fetch_by_id(source_id)
            if not source:
                yield f"event: error\ndata: {json.dumps({'message': f'Source {source_id} not found'})}\n\n"
                return
            sources = [source]
        else:
            sources = await source_repo.fetch_all(
                "SELECT DISTINCT s.* FROM crawl_sources s "
                "INNER JOIN pending_articles p ON s.id = p.source_id "
                "WHERE p.status = 'failed' "
                "ORDER BY s.site_name"
            )

        if not sources:
            yield f"event: start\ndata: {json.dumps({'sources_count': 0, 'message': 'No failed articles found to retry'})}\n\n"
            yield f"event: complete\ndata: {json.dumps({'retried': 0, 'failed': 0})}\n\n"
            return

        total_retried = 0
        total_failed = 0

        yield f"event: start\ndata: {json.dumps({'sources_count': len(sources), 'message': f'Starting retry for {len(sources)} sources'})}\n\n"

        for idx, source in enumerate(sources):
            source_id = source["id"]
            source_name = source["site_name"]

            try:
                parser_config = source.get("parser_config")
                if isinstance(parser_config, str):
                    parser_config = ParserConfig.model_validate_json(parser_config)

                articles = await pending_repo.get_by_source(
                    source_id,
                    status=PendingArticleStatus.FAILED,
                    limit=limit,
                )

                if not articles:
                    continue

                yield f"event: source_start\ndata: {json.dumps({'source_id': source_id, 'source_name': source_name, 'articles_count': len(articles), 'source_index': idx + 1})}\n\n"

                retried_count = 0
                failed_count = 0

                for pending_article in articles:
                    try:
                        article_id = pending_article["id"]
                        url = pending_article["url"]

                        # 重置状态为待爬
                        await pending_repo.update_status(article_id, PendingArticleStatus.PENDING)

                        # 检查 URL 是否已存在
                        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
                        existing = await article_repo.get_by_url_hash(url_hash)

                        if existing:
                            await pending_repo.update_status(article_id, PendingArticleStatus.COMPLETED)
                            retried_count += 1
                            yield f"event: article_skipped\ndata: {json.dumps({'url': url, 'reason': 'already_exists'})}\n\n"
                            continue

                        await pending_repo.update_status(article_id, PendingArticleStatus.CRAWLING)

                        async with UniversalScraper() as scraper:
                            article = await scraper.scrape(
                                url=url,
                                parser_config=parser_config,
                                source_id=source_id,
                            )

                        if article.error:
                            await pending_repo.update_status(article_id, PendingArticleStatus.FAILED)
                            failed_count += 1
                            yield f"event: article_failed\ndata: {json.dumps({'url': url, 'error': article.error})}\n\n"
                            continue

                        if not article.content or len(article.content) < 50:
                            await pending_repo.update_status(article_id, PendingArticleStatus.FAILED)
                            failed_count += 1
                            yield f"event: article_failed\ndata: {json.dumps({'url': url, 'error': 'Content too short'})}\n\n"
                            continue

                        create_data = ArticleCreate(
                            url=url,
                            title=article.title or pending_article.get("title") or "Untitled",
                            content=article.content,
                            publish_time=article.publish_time or pending_article.get("publish_time"),
                            author=article.author,
                            source_id=source_id,
                        )

                        new_article_id = await article_repo.create(create_data)
                        await pending_repo.update_status(article_id, PendingArticleStatus.COMPLETED)

                        retried_count += 1
                        yield f"event: article_success\ndata: {json.dumps({'article_id': new_article_id, 'url': url, 'title': article.title})}\n\n"

                    except Exception as e:
                        await pending_repo.update_status(pending_article["id"], PendingArticleStatus.FAILED)
                        failed_count += 1
                        yield f"event: article_failed\ndata: {json.dumps({'url': pending_article['url'], 'error': str(e)})}\n\n"

                    await asyncio.sleep(1)

                total_retried += retried_count
                total_failed += failed_count

                yield f"event: source_complete\ndata: {json.dumps({'source_id': source_id, 'source_name': source_name, 'retried': retried_count, 'failed': failed_count})}\n\n"

            except Exception as e:
                logger.error(f"Error processing source {source_name}: {e}", exc_info=True)
                continue

        yield f"event: complete\ndata: {json.dumps({'retried': total_retried, 'failed': total_failed, 'total': total_retried + total_failed})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# 单个 Sitemap 操作
# ============================================================================

@router.get("/{sitemap_id}", response_model=APIResponse[dict[str, Any]])
async def get_sitemap(
    sitemap_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取 Sitemap 详情"""
    repo = SitemapRepository(db)

    sitemap = await repo.get_by_id(sitemap_id)
    if not sitemap:
        raise NotFoundException(f"Sitemap {sitemap_id} not found")

    return APIResponse(success=True, data=dict(sitemap))


@router.delete("/{sitemap_id}", response_model=APIResponse[dict[str, Any]])
async def delete_sitemap(
    sitemap_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除 Sitemap"""
    repo = SitemapRepository(db)

    sitemap = await repo.get_by_id(sitemap_id)
    if not sitemap:
        raise NotFoundException(f"Sitemap {sitemap_id} not found")

    await repo.delete_by_id(sitemap_id)

    return APIResponse(success=True, data={"deleted_id": sitemap_id})


# ============================================================================
# Sitemap 操作
# ============================================================================

@router.post("/fetch-robots/{source_id}", response_model=APIResponse[dict[str, Any]])
async def fetch_robots_sitemaps(
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    从 robots.txt 获取 Sitemap

    解析指定源的 robots.txt，提取所有 Sitemap URL 并存储到数据库
    """
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


@router.post("/parse/{sitemap_id}", response_model=APIResponse[dict[str, Any]])
async def parse_sitemap(
    sitemap_id: int,
    recursive: bool = Query(default=True, description="是否递归解析子 Sitemap"),
    db: AsyncSession = Depends(get_db),
):
    """
    解析 Sitemap

    递归解析 Sitemap 索引，提取所有文章链接
    """
    service = SitemapService(db)
    try:
        result = await service.fetch_and_parse_sitemap(sitemap_id, recursive=recursive)

        return APIResponse(
            success=True,
            data={
                "sitemap_id": sitemap_id,
                "leaf_sitemaps": result.get("leaf_sitemaps", []),
                "articles_found": len(result.get("articles", [])),
            },
        )
    finally:
        await service.close()


@router.post("/import-articles/{sitemap_id}", response_model=APIResponse[dict[str, Any]])
async def import_sitemap_articles(
    sitemap_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    导入 Sitemap 文章到待爬表

    解析 Sitemap 并将文章链接添加到待爬队列
    """
    service = SitemapService(db)
    try:
        # 先解析 Sitemap
        parse_result = await service.fetch_and_parse_sitemap(sitemap_id, recursive=True)
        articles = parse_result.get("articles", [])

        # 导入到待爬表
        import_result = await service.import_articles_to_pending(articles)

        return APIResponse(
            success=True,
            data={
                "sitemap_id": sitemap_id,
                "articles_found": len(articles),
                "articles_imported": import_result["created"],
                "articles_existing": import_result["existing"],
            },
        )
    finally:
        await service.close()


@router.post("/sync-source/{source_id}", response_model=APIResponse[dict[str, Any]])
async def sync_source_sitemaps(
    source_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    同步源的所有 Sitemap 和文章

    完整流程：
    1. 从 robots.txt 获取 Sitemap
    2. 递归解析所有 Sitemap
    3. 提取文章链接到待爬表
    """
    service = SitemapService(db)
    try:
        result = await service.sync_source_sitemaps(source_id)

        return APIResponse(success=True, data=result)
    finally:
        await service.close()


@router.post("/add-custom", response_model=APIResponse[dict[str, Any]])
async def add_custom_sitemap(
    source_id: int | None = Query(default=None, description="源 ID（可选）"),
    sitemap_url: str = Query(..., description="Sitemap URL"),
    db: AsyncSession = Depends(get_db),
):
    """
    手动添加 Sitemap

    如果指定 source_id，添加到该源
    如果不指定 source_id，尝试从 URL 匹配现有源或创建新源
    """
    service = SitemapService(db)
    try:
        result = await service.add_custom_sitemap(source_id, sitemap_url)

        return APIResponse(success=True, data=result)
    finally:
        await service.close()
