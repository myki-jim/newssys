"""
联网搜索 API
/api/v1/search

集成搜索引擎，支持一键入库
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import APIResponse, BadRequestException, PaginationParams, SearchSaveRequest
from src.core.models import ArticleStatus
from src.services.search_engine import WebSearchEngine


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


async def get_search_engine() -> WebSearchEngine:  # type: ignore
    """获取搜索引擎实例"""
    async with WebSearchEngine() as engine:
        yield engine


# ============================================================================
# 搜索接口
# ============================================================================

@router.get("")
async def search_web(
    query: str = Query(..., min_length=2, description="搜索关键词"),
    time_range: str = Query(default="w", regex="^(d|w|m|y)$", description="时间范围"),
    max_results: int = Query(default=10, ge=1, le=50, description="最大结果数"),
    region: str = Query(default="us-en", description="地区设置"),
    engine: WebSearchEngine = Depends(get_search_engine),
):
    """
    执行联网搜索

    支持:
    - 时间范围过滤 (d=天, w=周, m=月, y=年)
    - 地区设置
    - 结果数量限制
    """
    results = await engine.search(
        query=query,
        time_range=time_range,
        max_results=max_results,
        region=region,
    )

    return APIResponse(
        success=True,
        data={
            "query": query,
            "time_range": time_range,
            "count": len(results),
            "results": [r.to_dict() for r in results],
        },
    )


@router.get("/fetch")
async def fetch_page_content(
    url: str = Query(..., description="目标 URL"),
    max_length: int = Query(default=5000, ge=500, le=50000, description="最大内容长度"),
    engine: WebSearchEngine = Depends(get_search_engine),
):
    """
    获取网页完整内容

    用于深度背景补充
    """
    content = await engine.fetch_page_content(url, max_length=max_length)

    if content is None:
        raise BadRequestException(f"Failed to fetch content from {url}")

    return APIResponse(
        success=True,
        data={
            "url": url,
            "content": content,
            "length": len(content),
        },
    )


# ============================================================================
# 一键入库
# ============================================================================

@router.post("/save", response_model=APIResponse[dict[str, Any]])
async def save_search_result(
    request: SearchSaveRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    搜索结果一键入库

    完整流程:
    1. 使用爬虫抓取完整内容
    2. 提取时间
    3. 保存到数据库
    """
    import hashlib

    from src.repository.article_repository import ArticleRepository
    from src.repository.source_repository import SourceRepository
    from src.services.universal_scraper import UniversalScraper
    from src.services.time_extractor import TimeExtractor
    from src.core.models import ArticleCreate, ParserConfig, RobotsStatus, SourceCreate

    # 检查 URL 是否已存在
    url_hash = hashlib.md5(request.url.encode('utf-8')).hexdigest()

    article_repo = ArticleRepository(db)
    existing = await article_repo.get_by_url_hash(url_hash)

    if existing:
        return APIResponse(
            success=True,
            data={
                "article": dict(existing),
                "status": "already_exists",
            },
        )

    # 推断源
    source_id = request.source_id
    from urllib.parse import urlparse

    # 处理 URL - 支持协议相对 URL (//domain.com/path)
    url = request.url.strip()

    # 处理协议相对 URL
    if url.startswith('//'):
        url = 'https:' + url
    # 添加协议前缀
    elif not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    parsed = urlparse(url)

    # 如果解析后的 netloc 为空，可能是 URL 格式有问题
    if not parsed.netloc:
        # 尝试从 path 中提取域名
        if '/' in parsed.path:
            # 可能是 "domain.com/path" 格式
            potential_domain = parsed.path.split('/')[0]
            if '.' in potential_domain:
                url = f'https://{parsed.path}'
                parsed = urlparse(url)

    # 验证 URL 是否有效
    if not parsed.netloc or parsed.netloc == '' or parsed.netloc == '/':
        raise BadRequestException(
            f"Invalid URL: '{request.url}'. Could not extract domain name."
        )

    base_url = f"{parsed.scheme}://{parsed.netloc}"

    if source_id is None:
        source_repo = SourceRepository(db)
        source = await source_repo.fetch_by_base_url(base_url)
        if source:
            source_id = source["id"]
            parser_config = source.get("parser_config")
            # 处理 parser_config 可能是字符串的情况
            if isinstance(parser_config, str):
                parser_config = ParserConfig.model_validate_json(parser_config)
        else:
            # 创建临时源
            site_name = parsed.netloc or base_url
            new_source = await source_repo.create(SourceCreate(
                site_name=site_name,
                base_url=base_url,
                parser_config=ParserConfig(
                    title_selector="h1",
                    content_selector="article, main",
                ),
                robots_status=RobotsStatus.PENDING,
                discovery_method="manual",
            ))
            source_id = new_source["id"]
            parser_config = ParserConfig(
                title_selector="h1",
                content_selector="article, main",
            )
    else:
        source_repo = SourceRepository(db)
        source = await source_repo.fetch_by_id(source_id)
        if source:
            parser_config = source.get("parser_config")
            # 处理 parser_config 可能是字符串的情况
            if isinstance(parser_config, str):
                parser_config = ParserConfig.model_validate_json(parser_config)
        else:
            parser_config = None

    # 使用 UniversalScraper 抓取内容
    try:
        # 首先解析真实 URL（DDG 可能返回跳转链接）
        from urllib.parse import unquote, parse_qs, urlparse
        real_url = url

        # 处理 DDG 跳转链接: https://duckduckgo.com/l/?uddg=<encoded_url>&rut=...
        if 'duckduckgo.com/l/' in url and 'uddg=' in url:
            logger.info(f"Detected DDG redirect URL: {url}")
            try:
                # 解析 URL 参数
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                if 'uddg' in params:
                    # 提取 uddg 参数并 decode
                    encoded_url = params['uddg'][0]
                    real_url = unquote(encoded_url)
                    logger.info(f"Decoded DDG URL: {url} -> {real_url}")
            except Exception as e:
                logger.error(f"Failed to decode DDG URL: {e}")
                real_url = url

        async with UniversalScraper() as scraper:
            article = await scraper.scrape(
                url=real_url,  # 使用解析后的真实 URL
                parser_config=parser_config or ParserConfig(
                    title_selector="h1",
                    content_selector="article, main",
                ),
                source_id=source_id,
            )

        # 使用抓取到的标题，如果没有则使用请求中的标题
        title = article.title or request.title

        # 严格的内容验证
        content = article.content
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
        elif not article.publish_time:
            error_msg = "未能提取发布时间"

        # 如果验证失败，抛出异常
        if error_msg:
            raise BadRequestException(f"内容验证失败: {error_msg}")

        # 创建文章
        create_data = ArticleCreate(
            url=url,
            title=title,
            content=content,
            publish_time=article.publish_time,
            author=article.author,
            source_id=source_id,
        )

        article_id = await article_repo.create(create_data)

        # Fetch the full article data
        article_data = await article_repo.get_by_id(article_id)

        logger.info(f"Saved search result as article: {article_id} with content length: {len(content)}, publish_time: {article.publish_time}")

        return APIResponse(
            success=True,
            data={
                "article": dict(article_data),
                "status": "created",
            },
        )

    except Exception as e:
        logger.error(f"Failed to fetch and save article from {url}: {e}", exc_info=True)

        # 即使失败也创建记录，标记为失败状态
        create_data = ArticleCreate(
            url=url,
            title=request.title or f"Failed: {url}",
            content=None,
            source_id=source_id,
        )

        article_id = await article_repo.create(create_data)

        # 更新为失败状态
        await article_repo.update_status(
            article_id,
            status=ArticleStatus.FAILED,
            error_message=str(e),
        )

        raise BadRequestException(f"Failed to fetch content from {url}: {e}")


@router.post("/save-batch", response_model=APIResponse[dict[str, Any]])
async def save_search_results_batch(
    query: str = Query(..., description="搜索关键词"),
    time_range: str = Query(default="w", description="时间范围"),
    max_results: int = Query(default=10, ge=1, le=50, description="最大结果数"),
    region: str = Query(default="us-en", description="地区设置"),
    db: AsyncSession = Depends(get_db),
    engine: WebSearchEngine = Depends(get_search_engine),
):
    """
    批量保存搜索结果

    执行搜索后，将所有结果批量保存到数据库（自动去重）

    返回:
    - total: 搜索结果总数
    - created: 新创建的文章数
    - existing: 已存在的文章数
    - failed: 保存失败的文章数
    - results: 所有文章的列表
    """
    import hashlib
    import asyncio

    from src.repository.article_repository import ArticleRepository
    from src.repository.source_repository import SourceRepository
    from src.services.universal_scraper import UniversalScraper
    from src.core.models import ParserConfig, RobotsStatus, SourceCreate
    from urllib.parse import urlparse, unquote, parse_qs

    # 执行搜索
    search_results = await engine.search(
        query=query,
        time_range=time_range,
        max_results=max_results,
        region=region,
    )

    article_repo = ArticleRepository(db)
    source_repo = SourceRepository(db)

    created_articles = []
    existing_articles = []
    failed_articles = []

    for result in search_results:
        try:
            # 处理 DDG URL
            url = result.url
            if 'duckduckgo.com/l/' in url and 'uddg=' in url:
                try:
                    parsed = urlparse(url)
                    params = parse_qs(parsed.query)
                    if 'uddg' in params:
                        url = unquote(params['uddg'][0])
                        logger.info(f"Decoded DDG URL: {result.url} -> {url}")
                except Exception:
                    pass

            # 检查URL是否已存在
            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
            existing = await article_repo.get_by_url_hash(url_hash)

            if existing:
                existing_articles.append(dict(existing))
                continue

            # 解析URL获取源
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"

            # 获取或创建源
            source = await source_repo.fetch_by_base_url(base_url)
            if source:
                source_id = source["id"]
                parser_config = source.get("parser_config")
                if isinstance(parser_config, str):
                    parser_config = ParserConfig.model_validate_json(parser_config)
            else:
                site_name = parsed.netloc
                new_source = await source_repo.create(SourceCreate(
                    site_name=site_name,
                    base_url=base_url,
                    parser_config=ParserConfig(
                        title_selector="h1",
                        content_selector="article, main",
                    ),
                    robots_status=RobotsStatus.PENDING,
                    discovery_method="manual",
                ))
                source_id = new_source["id"]
                parser_config = ParserConfig(
                    title_selector="h1",
                    content_selector="article, main",
                )

            # 爬取内容
            async with UniversalScraper() as scraper:
                article = await scraper.scrape(
                    url=url,
                    parser_config=parser_config,
                    source_id=source_id,
                )

            if article.error:
                failed_articles.append({
                    "url": url,
                    "title": result.title,
                    "error": article.error,
                })
                continue

            # 验证内容
            if not article.content or len(article.content) < 50:
                failed_articles.append({
                    "url": url,
                    "title": result.title,
                    "error": "Content too short or empty",
                })
                continue

            # 创建文章
            from src.core.models import ArticleCreate
            create_data = ArticleCreate(
                url=url,
                title=article.title or result.title,
                content=article.content,
                publish_time=article.publish_time,
                author=article.author,
                source_id=source_id,
            )

            article_id = await article_repo.create(create_data)
            article_data = await article_repo.get_by_id(article_id)

            if article_data:
                created_articles.append(dict(article_data))

        except Exception as e:
            logger.error(f"Failed to save {result.url}: {e}")
            failed_articles.append({
                "url": result.url,
                "title": result.title,
                "error": str(e),
            })

        # 添加延迟避免被封禁
        await asyncio.sleep(1)

    return APIResponse(
        success=True,
        data={
            "query": query,
            "total": len(search_results),
            "created": len(created_articles),
            "existing": len(existing_articles),
            "failed": len(failed_articles),
            "results": {
                "created": created_articles,
                "existing": existing_articles,
                "failed": failed_articles,
            },
        },
    )


# ============================================================================
# 上下文增强
# ============================================================================

@router.post("/enrich")
async def enrich_with_search(
    query: str,
    local_article_ids: list[int],
    time_range: str = Query(default="w", regex="^(d|w|m|y)$"),
    max_external_results: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """
    使用联网搜索增强本地数据

    支持:
    - 时间优先合并
    - 冲突检测
    - 去重
    """
    from src.services.search_engine import ContextEnricher, WebSearchEngine

    # 获取本地文章
    article_repo = ArticleRepository(db)
    local_articles = []
    for article_id in local_article_ids:
        article = await article_repo.fetch_by_id(article_id)
        if article:
            local_articles.append(dict(article))

    # 执行增强
    enricher = ContextEnricher()

    enrichment = await enricher.enrich_with_search(
        query=query,
        local_articles=local_articles,
        time_range=time_range,
        max_external_results=max_external_results,
    )

    return APIResponse(
        success=True,
        data={
            "query": query,
            "local_count": enrichment["local_count"],
            "external_count": enrichment["external_count"],
            "merged_count": len(enrichment["merged_articles"]),
            "conflicts_resolved": enrichment["conflicts_resolved"],
            "combined_context": enrichment["combined_context"],
            "external_results": enrichment["external_results"],
        },
    )
