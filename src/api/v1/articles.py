"""
文章管理 API
/api/v1/articles
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    APIResponse,
    ArticleFilter,
    BadRequestException,
    BulkDeleteRequest,
    BulkOperationResponse,
    DateRangeFilter,
    NotFoundException,
    PaginationParams,
    PaginatedResponse,
)
from src.core.models import Article, ArticleCreate, ArticleStatus, FetchStatus
from src.repository.article_repository import ArticleRepository


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
# CRUD 操作
# ============================================================================

@router.get("", response_model=APIResponse[PaginatedResponse[dict[str, Any]]])
async def list_articles(
    pagination: PaginationParams = Depends(),
    filter: ArticleFilter = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    获取文章列表（高性能分页）

    支持:
    - 多条件复合筛选
    - 服务端分页
    - 排序
    """
    repo = ArticleRepository(db)

    # 构建 WHERE 子句
    where_clauses = []
    params: dict[str, Any] = {}

    # 来源筛选
    if filter.source_ids:
        placeholders = ', '.join(f':sid_{i}' for i in range(len(filter.source_ids)))
        where_clauses.append(f"source_id IN ({placeholders})")
        for i, sid in enumerate(filter.source_ids):
            params[f'sid_{i}'] = sid

    # 状态筛选
    if filter.status:
        where_clauses.append("status = :status")
        params["status"] = filter.status

    if filter.fetch_status:
        where_clauses.append("fetch_status = :fetch_status")
        params["fetch_status"] = filter.fetch_status

    # 关键词搜索
    if filter.keyword:
        where_clauses.append("(title LIKE :keyword OR content LIKE :keyword)")
        params["keyword"] = f"%{filter.keyword}%"

    # URL Hash 精确查找
    if filter.url_hash:
        where_clauses.append("url_hash = :url_hash")
        params["url_hash"] = filter.url_hash

    # 日期范围
    if filter.date_range:
        if filter.date_range.start:
            where_clauses.append("created_at >= :date_start")
            params["date_start"] = filter.date_range.start
        if filter.date_range.end:
            where_clauses.append("created_at <= :date_end")
            params["date_end"] = filter.date_range.end

    # 构建完整 SQL
    where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

    # 获取总数
    count_sql = f"SELECT COUNT(*) as count FROM articles WHERE {where_clause}"
    total_result = await repo.fetch_one(count_sql, params)
    total = total_result["count"] if total_result else 0

    # 获取分页数据
    data_sql = f"""
        SELECT
            id, url_hash, url, title, content, publish_time,
            author, source_id, status, fetch_status,
            crawled_at, processed_at, created_at, updated_at
        FROM articles
        WHERE {where_clause}
        ORDER BY {pagination.sort_by or 'created_at'} {pagination.sort_order}
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = pagination.page_size
    params["offset"] = pagination.offset

    articles = await repo.fetch_all(data_sql, params)

    # 转换为字典
    items = [dict(a) for a in articles]

    paginated = PaginatedResponse.create(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    return APIResponse(success=True, data=paginated)


@router.get("/{article_id}", response_model=APIResponse[dict[str, Any]])
async def get_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单篇文章详情"""
    repo = ArticleRepository(db)

    article = await repo.fetch_by_id(article_id)
    if article is None:
        raise NotFoundException(f"Article {article_id} not found")

    return APIResponse(success=True, data=dict(article))


@router.post("", response_model=APIResponse[dict[str, Any]], status_code=status.HTTP_201_CREATED)
async def create_article(
    data: ArticleCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建文章（通常由爬虫自动调用）"""
    repo = ArticleRepository(db)

    # 检查 URL 哈希是否已存在
    import hashlib
    url_hash = hashlib.md5(data.url.encode('utf-8')).hexdigest()

    existing = await repo.fetch_by_url_hash(url_hash)
    if existing:
        # 已存在，返回现有文章
        return APIResponse(
            success=True,
            data=dict(existing),
        )

    # 创建新文章
    article = await repo.create(data)

    logger.info(f"Created article: {article.id} - {article.title[:50]}")

    return APIResponse(
        success=True,
        data=dict(article),
    )


@router.put("/{article_id}", response_model=APIResponse[dict[str, Any]])
async def update_article(
    article_id: int,
    title: str | None = None,
    content: str | None = None,
    publish_time: datetime | None = None,
    author: str | None = None,
    status: ArticleStatus | None = None,
    db: AsyncSession = Depends(get_db),
):
    """更新文章内容"""
    repo = ArticleRepository(db)

    article = await repo.fetch_by_id(article_id)
    if article is None:
        raise NotFoundException(f"Article {article_id} not found")

    # 构建更新数据
    update_data: dict[str, Any] = {}
    if title is not None:
        update_data["title"] = title
    if content is not None:
        update_data["content"] = content
    if publish_time is not None:
        update_data["publish_time"] = publish_time
    if author is not None:
        update_data["author"] = author
    if status is not None:
        update_data["status"] = status.value

    # 更新内容哈希
    if content is not None:
        from src.services.simhash import compute_content_hash
        update_data["content_hash"] = compute_content_hash(content)

    updated = await repo.update(article_id, update_data)

    return APIResponse(success=True, data=dict(updated))


@router.delete("/{article_id}", response_model=APIResponse[dict[str, Any]])
async def delete_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除文章"""
    repo = ArticleRepository(db)

    article = await repo.fetch_by_id(article_id)
    if article is None:
        raise NotFoundException(f"Article {article_id} not found")

    await repo.delete(article_id)

    logger.info(f"Deleted article: {article_id}")

    return APIResponse(success=True, data={"deleted_id": article_id})


# ============================================================================
# 单条采集
# ============================================================================

@router.post("/{article_id}/refetch", response_model=APIResponse[dict[str, Any]])
async def refetch_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    重新爬取文章内容

    用于修复之前抓取失败或内容不完整的文章
    """
    repo = ArticleRepository(db)

    # 获取现有文章
    article = await repo.fetch_by_id(article_id)
    if article is None:
        raise NotFoundException(f"Article {article_id} not found")

    # 更新状态为重试中
    await repo.update(article_id, {
        "fetch_status": FetchStatus.RETRY.value,
        "retry_count": article.get("retry_count", 0) + 1,
    })

    # 获取源配置
    from src.repository.source_repository import SourceRepository
    source_repo = SourceRepository(db)
    source = await source_repo.fetch_by_id(article["source_id"])

    if not source:
        raise NotFoundException(f"Source {article['source_id']} not found")

    # 执行重新爬取
    from src.services.universal_scraper import UniversalScraper
    from src.services.time_extractor import TimeExtractor

    try:
        time_extractor = TimeExtractor()
        logger.info(f"Starting refetch for article {article_id}, URL: {article['url']}")

        # 处理 parser_config - 可能是字符串或字典
        parser_config = source.get("parser_config")
        if isinstance(parser_config, str):
            # 如果是 JSON 字符串，需要反序列化
            from src.core.models import ParserConfig
            parser_config = ParserConfig.model_validate_json(parser_config)
        elif isinstance(parser_config, dict):
            from src.core.models import ParserConfig
            parser_config = ParserConfig(**parser_config)

        # 解析真实 URL（如果数据库中存的是 DDG 跳转链接）
        from urllib.parse import unquote, parse_qs, urlparse
        url_to_fetch = article["url"]

        # 处理 DDG 跳转链接: https://duckduckgo.com/l/?uddg=<encoded_url>&rut=...
        if 'duckduckgo.com/l/' in url_to_fetch and 'uddg=' in url_to_fetch:
            logger.info(f"Detected DDG redirect URL: {url_to_fetch}")
            try:
                # 解析 URL 参数
                parsed = urlparse(url_to_fetch)
                params = parse_qs(parsed.query)
                if 'uddg' in params:
                    # 提取 uddg 参数并 decode
                    encoded_url = params['uddg'][0]
                    url_to_fetch = unquote(encoded_url)
                    logger.info(f"Decoded DDG URL: {article['url']} -> {url_to_fetch}")
            except Exception as e:
                logger.error(f"Failed to decode DDG URL: {e}")

        # 使用 async with 正确初始化 scraper
        async with UniversalScraper() as scraper:
            # 抓取文章
            logger.info(f"Calling scraper.scrape with URL: {url_to_fetch}")
            scraped = await scraper.scrape(
                url=url_to_fetch,
                parser_config=parser_config or ParserConfig(
                    title_selector="h1",
                    content_selector="article, main",
                ),
                source_id=article["source_id"],
            )
            logger.info(f"Scrape completed. Title: {scraped.title}, Content length: {len(scraped.content) if scraped.content else 0}, Error: {scraped.error}")

            # 检查是否有爬取错误
            if scraped.error:
                logger.error(f"Scraping failed with error: {scraped.error}")
                await repo.update(article_id, {
                    "fetch_status": FetchStatus.FAILED.value,
                    "status": ArticleStatus.FAILED.value,
                    "error_msg": scraped.error,
                })
                raise BadRequestException(f"Failed to scrape article: {scraped.error}")

            # 严格验证内容
            content = scraped.content
            error_msg = None

            # 1. 检查内容是否为空或太短
            if not content or len(content) < 50:
                error_msg = f"内容太短 ({len(content) if content else 0} 字符 < 50)"

            # 2. 检查是否包含无效内容标记
            elif any(keyword in content.lower() for keyword in [
                "javascript", "enable javascript", "请启用 javascript",
                "请开启javascript", "需要javascript", "enable cookies"
            ]):
                error_msg = "内容包含无效标记 (javascript/cookies)"

            # 3. 检查是否提取到时间
            elif not scraped.publish_time:
                error_msg = "未能提取发布时间"

            # 如果验证失败
            if error_msg:
                logger.warning(f"Content validation failed for article {article_id}: {error_msg}")
                await repo.update(article_id, {
                    "fetch_status": FetchStatus.FAILED.value,
                    "status": ArticleStatus.FAILED.value,
                    "error_msg": error_msg,
                })
                raise BadRequestException(f"Content validation failed: {error_msg}")

            # 时间提取（后备方案）
            publish_time = scraped.publish_time
            if publish_time is None:
                publish_time = time_extractor.extract_publish_time(
                    html_content="",
                    url=article["url"],
                )

            # 验证通过，更新文章内容
            update_data = {
                "title": scraped.title or article["title"],
                "content": content,
                "author": scraped.author or article.get("author"),
                "publish_time": publish_time,
                "status": ArticleStatus.RAW.value,
                "fetch_status": FetchStatus.SUCCESS.value,
                "error_msg": None,
            }

            updated = await repo.update(article_id, update_data)

            logger.info(f"Successfully refetched article {article_id}: content length {len(content)}")

            return APIResponse(
                success=True,
                data={
                    "article": dict(updated),
                    "status": "refetched",
                },
            )

    except Exception as e:
        logger.error(f"Failed to refetch article {article_id}: {e}", exc_info=True)

        # 更新为失败状态
        await repo.update(article_id, {
            "fetch_status": FetchStatus.FAILED.value,
            "status": ArticleStatus.FAILED.value,
            "error_msg": str(e),
        })

        raise BadRequestException(f"Failed to refetch article: {e}")

@router.post("/sync-all", response_model=APIResponse[dict[str, Any]])
async def sync_all_articles(
    db: AsyncSession = Depends(get_db),
):
    """
    一键同步所有文章

    重新爬取所有没有内容或内容为空的文章
    """
    repo = ArticleRepository(db)

    # 查找所有需要同步的文章（content 为空或长度小于 100）
    sql = """
        SELECT id, url, source_id, title
        FROM articles
        WHERE content IS NULL OR length(content) < 100
        ORDER BY id ASC
        LIMIT 50
    """
    articles = await repo.fetch_all(sql, {})

    if not articles:
        return APIResponse(
            success=True,
            data={
                "message": "没有需要同步的文章",
                "total": 0,
                "success": 0,
                "failed": 0,
            },
        )

    logger.info(f"Starting sync for {len(articles)} articles")

    success_count = 0
    failed_count = 0
    errors = []

    # 获取源配置
    from src.repository.source_repository import SourceRepository
    source_repo = SourceRepository(db)

    for article in articles:
        article_id = article["id"]
        url = article["url"]

        try:
            logger.info(f"Syncing article {article_id}: {url}")

            # 获取源配置
            source = await source_repo.fetch_by_id(article["source_id"])
            if not source:
                logger.error(f"Source {article['source_id']} not found for article {article_id}")
                failed_count += 1
                errors.append({"id": article_id, "error": "Source not found"})
                continue

            # 处理 parser_config
            parser_config = source.get("parser_config")
            if isinstance(parser_config, str):
                from src.core.models import ParserConfig
                parser_config = ParserConfig.model_validate_json(parser_config)
            elif isinstance(parser_config, dict):
                from src.core.models import ParserConfig
                parser_config = ParserConfig(**parser_config)

            # 解析 DDG URL
            from urllib.parse import unquote, parse_qs, urlparse
            url_to_fetch = url

            if 'duckduckgo.com/l/' in url_to_fetch and 'uddg=' in url_to_fetch:
                try:
                    parsed = urlparse(url_to_fetch)
                    params = parse_qs(parsed.query)
                    if 'uddg' in params:
                        encoded_url = params['uddg'][0]
                        url_to_fetch = unquote(encoded_url)
                        logger.info(f"Decoded DDG URL: {url} -> {url_to_fetch}")
                except Exception as e:
                    logger.error(f"Failed to decode DDG URL: {e}")

            # 爬取文章
            from src.services.universal_scraper import UniversalScraper
            async with UniversalScraper() as scraper:
                scraped = await scraper.scrape(
                    url=url_to_fetch,
                    parser_config=parser_config or ParserConfig(
                        title_selector="h1",
                        content_selector="article, main",
                    ),
                    source_id=article["source_id"],
                )

                # 检查是否成功
                if scraped.error:
                    logger.error(f"Failed to scrape article {article_id}: {scraped.error}")
                    failed_count += 1
                    errors.append({"id": article_id, "error": scraped.error})

                    # 更新为失败状态
                    await repo.update(article_id, {
                        "fetch_status": FetchStatus.FAILED.value,
                        "error_msg": scraped.error,
                    })
                else:
                    # 更新文章内容
                    update_data = {
                        "title": scraped.title or article["title"],
                        "content": scraped.content,
                        "author": scraped.author,
                        "fetch_status": FetchStatus.SUCCESS.value if scraped.content else FetchStatus.FAILED.value,
                        "error_msg": None,
                    }

                    await repo.update(article_id, update_data)

                    if scraped.content and len(scraped.content) > 100:
                        success_count += 1
                        logger.info(f"Successfully synced article {article_id}: content length {len(scraped.content)}")
                    else:
                        failed_count += 1
                        logger.warning(f"Article {article_id} synced but content is too short")
                        errors.append({"id": article_id, "error": "Content too short or empty"})

        except Exception as e:
            logger.error(f"Failed to sync article {article_id}: {e}", exc_info=True)
            failed_count += 1
            errors.append({"id": article_id, "error": str(e)})

    logger.info(f"Sync completed: {success_count} success, {failed_count} failed")

    return APIResponse(
        success=True,
        data={
            "message": f"同步完成：成功 {success_count} 条，失败 {failed_count} 条",
            "total": len(articles),
            "success": success_count,
            "failed": failed_count,
            "errors": errors[:10],  # 只返回前10个错误
        },
    )

@router.post("/fetch/single", response_model=APIResponse[dict[str, Any]])
async def fetch_single_article(
    url: str = Body(..., embed=True),
    source_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    单条文章采集入口（与搜索入库使用相同的管线）

    完整流程: 爬取 -> 提取 -> 验证 -> 入库
    """
    # 检查 URL 是否已存在
    import hashlib
    from urllib.parse import unquote, parse_qs, urlparse

    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()

    repo = ArticleRepository(db)
    existing = await repo.fetch_by_url_hash(url_hash)

    if existing:
        return APIResponse(
            success=True,
            data={
                "article": dict(existing),
                "status": "already_exists",
            },
        )

    # 获取或推断源
    from src.repository.source_repository import SourceRepository
    source_repo = SourceRepository(db)

    if source_id is None:
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        source = await source_repo.fetch_by_base_url(base_url)
        if source:
            source_id = source["id"]
        else:
            # 创建新源
            from src.core.models import ParserConfig, SourceCreate
            new_source = await source_repo.create(SourceCreate(
                site_name=parsed.netloc,
                base_url=base_url,
                parser_config=ParserConfig(
                    title_selector="h1",
                    content_selector="article, main",
                ),
                enabled=False,
            ))
            source_id = new_source["id"]

    # 获取源配置
    source = await source_repo.fetch_by_id(source_id)
    if not source:
        raise NotFoundException(f"Source {source_id} not found")

    # 解析 DDG URL（如果有）
    real_url = url
    if 'duckduckgo.com/l/' in url and 'uddg=' in url:
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if 'uddg' in params:
                real_url = unquote(params['uddg'][0])
        except Exception:
            pass

    # 使用 UniversalScraper 抓取内容
    from src.services.universal_scraper import UniversalScraper

    try:
        async with UniversalScraper() as scraper:
            article = await scraper.scrape(
                url=real_url,
                parser_config=ParserConfig(
                    title_selector="h1",
                    content_selector="article, main",
                ),
                source_id=source_id,
            )

        # 严格的内容验证（与搜索入库一致）
        content = article.content
        error_msg = None

        # 1. 检查内容是否为空或太短
        if not content or len(content) < 50:
            error_msg = f"内容太短 ({len(content) if content else 0} 字符 < 50)"

        # 2. 检查是否包含无效内容标记
        elif any(keyword in (content or "").lower() for keyword in [
            "javascript", "enable javascript", "请启用 javascript",
            "请开启javascript", "需要javascript", "enable cookies"
        ]):
            error_msg = "内容包含无效标记 (javascript/cookies)"

        # 3. 检查是否提取到时间
        elif not article.publish_time:
            error_msg = "未能提取发布时间"

        # 如果验证失败，抛出异常
        if error_msg:
            raise BadRequestException(f"内容验证失败: {error_msg}")

        # 创建文章
        create_data = ArticleCreate(
            url=url,
            title=article.title or real_url,
            content=content,
            publish_time=article.publish_time,
            author=article.author,
            source_id=source_id,
        )

        article_id = await repo.create(create_data)

        # 获取完整文章数据
        article_data = await repo.get_by_id(article_id)

        logger.info(f"Saved article: {article_id} with content length: {len(content)}, publish_time: {article.publish_time}")

        return APIResponse(
            success=True,
            data={
                "article": dict(article_data),
                "status": "created",
            },
        )

    except BadRequestException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch article {url}: {e}", exc_info=True)
        raise BadRequestException(f"Failed to fetch article: {e}")


# ============================================================================
# 批量操作
# ============================================================================

@router.post("/bulk/retry", response_model=APIResponse[BulkOperationResponse])
async def bulk_retry_articles(
    article_ids: list[int] | None = None,
    filter: ArticleFilter | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    批量重试失败的文章

    支持:
    - 指定 ID 列表
    - 按筛选条件自动查找
    """
    repo = ArticleRepository(db)

    # 如果未指定 IDs，按筛选条件查找
    if article_ids is None:
        if filter is None:
            # 默认重试所有失败的文章
            filter = ArticleFilter(
                status=ArticleStatus.FAILED.value,
                fetch_status=FetchStatus.FAILED.value,
            )

        # 获取符合筛选的文章 ID
        where_clauses = ["status = :status", "fetch_status = :fetch_status"]
        params = {"status": ArticleStatus.FAILED.value, "fetch_status": FetchStatus.FAILED.value}

        sql = f"SELECT id FROM articles WHERE {' AND '.join(where_clauses)}"
        results = await repo.fetch_all(sql, params)
        article_ids = [r["id"] for r in results]

    success_count = 0
    failed_count = 0
    errors = []

    for article_id in article_ids:
        try:
            article = await repo.fetch_by_id(article_id)
            if not article:
                errors.append({"id": article_id, "error": "Not found"})
                failed_count += 1
                continue

            # 重置状态
            await repo.update(article_id, {
                "fetch_status": FetchStatus.PENDING.value,
                "retry_count": article.retry_count + 1,
                "last_retry_at": datetime.now(),
            })

            # TODO: 重新加入抓取队列
            success_count += 1

        except Exception as e:
            logger.error(f"Failed to retry article {article_id}: {e}")
            errors.append({"id": article_id, "error": str(e)})
            failed_count += 1

    return APIResponse(
        success=True,
        data=BulkOperationResponse(
            success_count=success_count,
            failed_count=failed_count,
            errors=errors,
        ),
    )


@router.post("/bulk/delete", response_model=APIResponse[BulkOperationResponse])
async def bulk_delete_articles(
    request: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """批量删除文章"""
    repo = ArticleRepository(db)

    success_count = 0
    failed_count = 0
    errors = []

    for article_id in request.article_ids:
        try:
            await repo.delete(article_id)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to delete article {article_id}: {e}")
            errors.append({"id": article_id, "error": str(e)})
            failed_count += 1

    return APIResponse(
        success=True,
        data=BulkOperationResponse(
            success_count=success_count,
            failed_count=failed_count,
            errors=errors,
        ),
    )


@router.post("/cleanup", response_model=APIResponse[BulkOperationResponse])
async def cleanup_articles(
    db: AsyncSession = Depends(get_db),
):
    """
    清理低质量文章

    清理条件:
    1. 内容长度 < 50 字符
    2. 没有发布时间 (publish_time IS NULL)
    3. 发布时间在一年之外 (publish_time < now() - 365 days OR publish_time > now() + 365 days)
    """
    from datetime import timedelta

    repo = ArticleRepository(db)

    # 计算一年前和一年后的时间
    one_year_ago = datetime.now() - timedelta(days=365)
    one_year_future = datetime.now() + timedelta(days=365)

    # 构建清理 SQL
    cleanup_sql = """
        SELECT id FROM articles WHERE
            LENGTH(COALESCE(content, '')) < 50
            OR publish_time IS NULL
            OR publish_time < :one_year_ago
            OR publish_time > :one_year_future
    """

    # 查询需要清理的文章
    articles_to_cleanup = await repo.fetch_all(
        cleanup_sql,
        {"one_year_ago": one_year_ago, "one_year_future": one_year_future}
    )

    success_count = 0
    failed_count = 0
    errors = []

    for article in articles_to_cleanup:
        try:
            await repo.delete(article["id"])
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to delete article {article['id']}: {e}")
            errors.append({"id": article["id"], "error": str(e)})
            failed_count += 1

    logger.info(f"Cleaned up {success_count} articles, {failed_count} failed")

    return APIResponse(
        success=True,
        data=BulkOperationResponse(
            success_count=success_count,
            failed_count=failed_count,
            errors=errors,
        ),
    )


# ============================================================================
# 相似文章检测
# ============================================================================

@router.get("/{article_id}/similar", response_model=APIResponse[list[dict[str, Any]]])
async def get_similar_articles(
    article_id: int,
    limit: int = Query(default=10, ge=1, le=50, description="返回数量"),
    threshold: float = Query(default=0.85, ge=0, le=1, description="相似度阈值"),
    db: AsyncSession = Depends(get_db),
):
    """
    查找相似文章（基于 SimHash）

    用于内容去重和关联发现
    """
    repo = ArticleRepository(db)

    article = await repo.fetch_by_id(article_id)
    if article is None:
        raise NotFoundException(f"Article {article_id} not found")

    # 计算 SimHash
    from src.services.simhash import TextCluster
    cluster = TextCluster(similarity_threshold=threshold)

    # 获取所有文章进行比对（实际应该用更高效的方式）
    all_articles_sql = "SELECT id, title, content FROM articles WHERE id != :id LIMIT 1000"
    all_articles = await repo.fetch_all(all_articles_sql, {"id": article_id})

    # 查找相似文章
    query_text = f"{article.title}. {article.content or ''}"[:500]

    similar_ids = cluster.find_nearest(
        query=query_text,
        candidates=[f"{a['title']}. {a.get('content', '') or ''}"[:500] for a in all_articles],
        candidate_ids=[a["id"] for a in all_articles],
        top_k=limit,
    )

    # 过滤低于阈值的结果
    similar_articles = []
    for cand_id, similarity in similar_ids:
        if similarity >= threshold:
            similar_article = await repo.fetch_by_id(cand_id)
            if similar_article:
                similar_articles.append({
                    **dict(similar_article),
                    "similarity": similarity,
                })

    return APIResponse(success=True, data=similar_articles)


# ============================================================================
# 状态统计
# ============================================================================

@router.get("/stats/by-status", response_model=APIResponse[dict[str, Any]])
async def get_status_stats(
    db: AsyncSession = Depends(get_db),
):
    """获取按状态分组统计"""
    repo = ArticleRepository(db)

    sql = """
        SELECT
            status,
            fetch_status,
            COUNT(*) as count
        FROM articles
        GROUP BY status, fetch_status
        ORDER BY status, fetch_status
    """

    results = await repo.fetch_all(sql, {})

    stats = {
        "by_status": {},
        "by_fetch_status": {},
        "total": 0,
    }

    for row in results:
        status_val = row["status"]
        fetch_status_val = row["fetch_status"]
        count = row["count"]

        if status_val not in stats["by_status"]:
            stats["by_status"][status_val] = 0
        stats["by_status"][status_val] += count

        if fetch_status_val not in stats["by_fetch_status"]:
            stats["by_fetch_status"][fetch_status_val] = 0
        stats["by_fetch_status"][fetch_status_val] += count

        stats["total"] += count

    return APIResponse(success=True, data=stats)
