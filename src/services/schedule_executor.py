"""
定时任务执行器
负责执行各类定时任务
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse, unquote, parse_qs

from src.core.database import get_async_session
from src.core.models import ArticleCreate, SourceCreate
from src.repository.article_repository import ArticleRepository
from src.repository.keyword_repository import KeywordRepository
from src.repository.pending_article_repository import PendingArticleRepository
from src.repository.schedule_repository import ScheduleRepository
from src.repository.sitemap_repository import SitemapRepository
from src.repository.source_repository import SourceRepository
from src.services.search_engine import WebSearchEngine
from src.services.sitemap_service import SitemapService
from src.services.universal_scraper import UniversalScraper

logger = logging.getLogger(__name__)


class ScheduleExecutor:
    """定时任务执行器"""

    async def execute_schedule(self, schedule_id: int, task_id: int) -> None:
        """执行定时任务"""
        async with get_async_session() as db:
            schedule_repo = ScheduleRepository(db)
            schedule = await schedule_repo.get_by_id(schedule_id)

            if not schedule:
                logger.error(f"定时任务不存在: {schedule_id}")
                return

            try:
                # 更新执行状态
                await schedule_repo.increment_execution_count(schedule_id)

                # 根据类型执行不同的任务
                if schedule["schedule_type"] == "sitemap_crawl":
                    await self._execute_sitemap_crawl(db, schedule)
                elif schedule["schedule_type"] == "article_crawl":
                    await self._execute_article_crawl(db, schedule)
                elif schedule["schedule_type"] == "keyword_search":
                    await self._execute_keyword_search(db, schedule)
                else:
                    raise ValueError(f"未知的任务类型: {schedule['schedule_type']}")

                # 计算下次运行时间
                next_run = datetime.now() + timedelta(minutes=schedule["interval_minutes"])
                await schedule_repo.update(
                    schedule_id,
                    {
                        "next_run_at": next_run.isoformat(),
                        "last_status": "success",
                        "last_error": None,
                    },
                )

                logger.info(f"定时任务执行成功: {schedule['name']}")

            except Exception as e:
                logger.error(f"定时任务执行失败: {schedule['name']}, 错误: {e}")
                await schedule_repo.update(
                    schedule_id,
                    {
                        "last_status": "failed",
                        "last_error": str(e),
                    },
                )
                raise

    async def _execute_sitemap_crawl(self, db, schedule: dict) -> None:
        """执行 Sitemap 爬取任务 - 爬取所有 sitemap"""
        sitemap_service = SitemapService(db)

        # 获取所有 sitemap（与启用的源关联的）
        from sqlalchemy import text

        result = await db.execute(
            text("""
                SELECT s.* FROM sitemaps s
                INNER JOIN crawl_sources c ON s.source_id = c.id
                WHERE c.enabled = 1
                ORDER BY s.id
            """)
        )
        sitemaps = []
        for row in result.fetchall():
            sitemaps.append({col: value for col, value in row._mapping.items()})

        if not sitemaps:
            logger.info("没有 sitemap 可爬取")
            return

        total_found = 0
        total_imported = 0

        for sitemap in sitemaps:
            try:
                # 解析 Sitemap
                parse_result = await sitemap_service.fetch_and_parse_sitemap(
                    sitemap["id"], recursive=True
                )
                articles = parse_result.get("articles", [])

                # 导入到待爬表
                import_result = await sitemap_service.import_articles_to_pending(articles)

                total_found += len(articles)
                total_imported += import_result["created"]

                logger.info(
                    f"Sitemap {sitemap['id']} 爬取完成: 发现 {len(articles)} 篇, 导入 {import_result['created']} 篇"
                )

            except Exception as e:
                logger.error(f"Sitemap {sitemap['id']} 爬取失败: {e}")
                continue

        logger.info(
            f"所有 Sitemap 爬取完成: 共 {len(sitemaps)} 个, 发现 {total_found} 篇, 导入 {total_imported} 篇"
        )

    async def _execute_article_crawl(self, db, schedule: dict) -> None:
        """执行文章自动爬取任务 - 遍历所有有待爬文章的源"""
        from src.core.models import ParserConfig, PendingArticleStatus
        from src.repository.source_repository import SourceRepository

        config = schedule.get("config", {})
        batch_size = config.get("batch_size", 50)

        pending_repo = PendingArticleRepository(db)
        article_repo = ArticleRepository(db)
        source_repo = SourceRepository(db)

        # 获取所有有待爬文章的源
        from sqlalchemy import text

        result = await db.execute(
            text(
                "SELECT DISTINCT s.* FROM crawl_sources s "
                "INNER JOIN pending_articles p ON s.id = p.source_id "
                "WHERE p.status = 'pending' "
                "ORDER BY s.site_name"
            )
        )
        sources = []
        for row in result.fetchall():
            sources.append({col: value for col, value in row._mapping.items()})

        if not sources:
            logger.info("没有有待爬文章的源")
            return

        total_crawled = 0
        total_failed = 0
        total_skipped = 0

        for source in sources:
            try:
                source_id = source["id"]
                source_name = source["site_name"]

                # 解析 parser_config
                parser_config = source.get("parser_config")
                if isinstance(parser_config, str):
                    parser_config = ParserConfig.model_validate_json(parser_config)

                # 获取该源的待爬文章
                articles = await pending_repo.get_by_source(
                    source_id, status=PendingArticleStatus.PENDING, limit=batch_size
                )

                if not articles:
                    continue

                logger.info(f"开始爬取源 {source_name} (ID: {source_id}), 待爬文章: {len(articles)} 篇")

                crawled_count = 0
                failed_count = 0
                skipped_count = 0

                for pending_article in articles:
                    try:
                        article_id = pending_article["id"]
                        url = pending_article["url"]

                        # 检查 URL 是否已存在
                        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
                        existing = await article_repo.get_by_url_hash(url_hash)

                        if existing:
                            await pending_repo.update_status(article_id, PendingArticleStatus.COMPLETED)
                            skipped_count += 1
                            continue

                        # 更新状态为爬取中
                        await pending_repo.update_status(article_id, PendingArticleStatus.CRAWLING)

                        # 使用 UniversalScraper 抓取内容
                        async with UniversalScraper() as scraper:
                            article = await scraper.scrape(
                                url=url, parser_config=parser_config, source_id=source_id
                            )

                        if article.error:
                            await pending_repo.update_status(article_id, PendingArticleStatus.FAILED)
                            failed_count += 1
                            logger.warning(f"爬取失败: {url}, 错误: {article.error}")
                            continue

                        # 验证内容
                        if not article.content or len(article.content) < 50:
                            await pending_repo.update_status(article_id, PendingArticleStatus.FAILED)
                            failed_count += 1
                            logger.warning(f"内容太短: {url}")
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
                        await pending_repo.update_status(article_id, PendingArticleStatus.COMPLETED)

                        crawled_count += 1
                        logger.info(f"成功爬取文章 {new_article_id}: {url}")

                    except Exception as e:
                        await pending_repo.update_status(pending_article["id"], PendingArticleStatus.FAILED)
                        failed_count += 1
                        logger.error(f"爬取文章失败: {pending_article['url']}, 错误: {e}")

                    # 添加延迟避免被封禁
                    await asyncio.sleep(1)

                total_crawled += crawled_count
                total_failed += failed_count
                total_skipped += skipped_count

                logger.info(
                    f"源 {source_name} 爬取完成: 成功 {crawled_count} 篇, 失败 {failed_count} 篇, 跳过 {skipped_count} 篇"
                )

            except Exception as e:
                logger.error(f"爬取源 {source['site_name']} 失败: {e}")
                continue

        logger.info(
            f"所有源爬取完成: 共 {len(sources)} 个源, 成功 {total_crawled} 篇, 失败 {total_failed} 篇, 跳过 {total_skipped} 篇"
        )

    async def _execute_keyword_search(self, db, schedule: dict) -> None:
        """执行关键词搜索任务 - 遍历所有激活的关键词"""
        from urllib.parse import urlparse, unquote, parse_qs

        from src.core.models import ArticleCreate, ParserConfig, RobotsStatus, SourceCreate

        # 获取所有激活的关键词
        keywords = await KeywordRepository(db).get_active_keywords()

        if not keywords:
            logger.info("没有激活的关键词")
            return

        article_repo = ArticleRepository(db)
        source_repo = SourceRepository(db)
        search_engine = WebSearchEngine()

        total_searched = 0
        total_saved = 0

        for keyword in keywords:
            try:
                if not keyword["is_active"]:
                    continue

                logger.info(f"开始搜索关键词: {keyword['keyword']}")

                # 执行搜索
                results = await search_engine.search(
                    query=keyword["keyword"],
                    time_range=keyword["time_range"],
                    max_results=keyword["max_results"],
                    region=keyword["region"],
                )

                total_searched += len(results)
                saved_count = 0

                # 保存搜索结果
                for result in results:
                    try:
                        # 处理 DDG URL
                        url = result.url
                        if "duckduckgo.com/l/" in url and "uddg=" in url:
                            try:
                                parsed = urlparse(url)
                                params = parse_qs(parsed.query)
                                if "uddg" in params:
                                    url = unquote(params["uddg"][0])
                            except Exception:
                                pass

                        # 检查 URL 是否已存在
                        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
                        existing = await article_repo.get_by_url_hash(url_hash)

                        if existing:
                            continue

                        # 解析 URL 获取源
                        parsed = urlparse(url)
                        base_url = f"{parsed.scheme}://{parsed.netloc}"

                        # 获取或创建源
                        source = await source_repo.fetch_by_base_url(base_url)
                        if source:
                            source_id = source["id"]
                            parser_config = source.get("parser_config")
                            if isinstance(parser_config, str):
                                from src.core.models import ParserConfig

                                parser_config = ParserConfig.model_validate_json(parser_config)
                        else:
                            site_name = parsed.netloc
                            new_source = await source_repo.create(
                                SourceCreate(
                                    site_name=site_name,
                                    base_url=base_url,
                                    parser_config=ParserConfig(
                                        title_selector="h1",
                                        content_selector="article, main",
                                    ),
                                    robots_status=RobotsStatus.PENDING,
                                    discovery_method="manual",
                                )
                            )
                            source_id = new_source["id"]
                            parser_config = ParserConfig(
                                title_selector="h1",
                                content_selector="article, main",
                            )

                        # 爬取内容
                        async with UniversalScraper() as scraper:
                            article = await scraper.scrape(
                                url=url, parser_config=parser_config, source_id=source_id
                            )

                        if article.error:
                            logger.warning(f"爬取失败: {url}, 错误: {article.error}")
                            continue

                        # 验证内容
                        if not article.content or len(article.content) < 50:
                            logger.warning(f"内容太短: {url}")
                            continue

                        # 创建文章
                        create_data = ArticleCreate(
                            url=url,
                            title=article.title or result.title,
                            content=article.content,
                            publish_time=article.publish_time or result.published_date,
                            author=article.author,
                            source_id=source_id,
                        )

                        await article_repo.create(create_data)
                        saved_count += 1

                    except Exception as e:
                        logger.warning(f"保存搜索结果失败: {result.url}, 错误: {e}")
                        continue

                # 更新搜索次数
                await KeywordRepository(db).increment_search_count(keyword["id"])

                total_saved += saved_count
                logger.info(
                    f"关键词 {keyword['keyword']} 搜索完成: 搜索到 {len(results)} 篇, 保存 {saved_count} 篇"
                )

            except Exception as e:
                logger.error(f"关键词 {keyword['keyword']} 搜索失败: {e}")
                continue

        logger.info(
            f"所有关键词搜索完成: 共 {len(keywords)} 个, 搜索到 {total_searched} 篇, 保存 {total_saved} 篇"
        )
