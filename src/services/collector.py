"""
爬虫调度器
负责协调爬虫源发现、内容爬取和数据存储
支持 Robots 协议和 Sitemap 自动发现
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import ArticleCreate, ArticleStatus, RobotsStatus
from src.infrastructure.database import db_manager, init_db, close_db
from src.repository.article_repository import ArticleRepository
from src.repository.source_repository import SourceRepository
from src.services.scraper import UniversalScraper
from src.services.site_discovery import SiteDiscovery
from src.services.robots_handler import get_robots_handler


logger = logging.getLogger(__name__)


class CollectorConfig:
    """调度器配置"""

    # 默认并发配置
    DEFAULT_CONCURRENT_SOURCES = 3  # 同时处理的爬虫源数量
    DEFAULT_CONCURRENT_ARTICLES = 5  # 每个源同时爬取的文章数量
    DEFAULT_MAX_DISCOVER_PAGES = 3  # 每个源最大翻页数
    DEFAULT_MAX_ARTICLES_PER_SOURCE = 50  # 每个源最大爬取文章数

    # Robots 默认延迟
    DEFAULT_CRAWL_DELAY = 1.0  # 默认延迟秒数


class NewsCollector:
    """
    新闻采集调度器
    协调爬虫源、爬虫服务和数据存储
    支持 Robots 协议和 Sitemap 自动发现
    """

    def __init__(
        self,
        concurrent_sources: int = CollectorConfig.DEFAULT_CONCURRENT_SOURCES,
        concurrent_articles: int = CollectorConfig.DEFAULT_CONCURRENT_ARTICLES,
        max_discover_pages: int = CollectorConfig.DEFAULT_MAX_DISCOVER_PAGES,
        max_articles_per_source: int = CollectorConfig.DEFAULT_MAX_ARTICLES_PER_SOURCE,
        respect_robots: bool = True,
    ) -> None:
        """
        初始化调度器

        Args:
            concurrent_sources: 并发处理的爬虫源数量
            concurrent_articles: 每个源并发爬取的文章数量
            max_discover_pages: 每个源最大翻页页数
            max_articles_per_source: 每个源最大爬取文章数
            respect_robots: 是否遵守 Robots 协议
        """
        self.concurrent_sources = concurrent_sources
        self.concurrent_articles = concurrent_articles
        self.max_discover_pages = max_discover_pages
        self.max_articles_per_source = max_articles_per_source
        self.respect_robots = respect_robots

        # 获取全局 Robots 处理器
        self.robots_handler = get_robots_handler()

    async def run_once(self, initialize_sources: bool = True) -> dict[str, Any]:
        """
        执行一次采集任务

        Args:
            initialize_sources: 是否初始化源（检查 robots.txt 和 sitemap）

        Returns:
            采集结果统计
        """
        stats = {
            'sources_processed': 0,
            'sources_initialized': 0,
            'urls_discovered': 0,
            'articles_crawled': 0,
            'articles_saved': 0,
            'articles_skipped': 0,
            'robots_denied': 0,
            'errors': [],
            'started_at': datetime.now(),
        }

        logger.info("Starting news collection...")

        async with db_manager.session() as session:
            source_repo = SourceRepository(session)
            article_repo = ArticleRepository(session)

            # 获取所有启用的爬虫源
            sources = await source_repo.list_all(enabled_only=True)
            stats['sources_processed'] = len(sources)

            logger.info(f"Found {len(sources)} enabled sources")

            if not sources:
                logger.warning("No enabled sources found")
                return stats

            # 初始化源（检查 robots.txt 和 sitemap）
            if initialize_sources:
                stats['sources_initialized'] = await self._initialize_sources(
                    sources, session
                )

            # 并发处理每个源
            semaphore = asyncio.Semaphore(self.concurrent_sources)

            async def process_source(source_dict: dict[str, Any]) -> dict[str, Any]:
                async with semaphore:
                    return await self._process_source(
                        source_dict,
                        article_repo,
                        source_repo,
                    )

            # 转换 source dict 为 domain model
            tasks = []
            for source_dict in sources:
                tasks.append(process_source(source_dict))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 汇总结果
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Source processing failed: {result}")
                    stats['errors'].append(str(result))
                elif isinstance(result, dict):
                    stats['urls_discovered'] += result.get('urls_discovered', 0)
                    stats['articles_crawled'] += result.get('articles_crawled', 0)
                    stats['articles_saved'] += result.get('articles_saved', 0)
                    stats['articles_skipped'] += result.get('articles_skipped', 0)
                    stats['robots_denied'] += result.get('robots_denied', 0)

        stats['completed_at'] = datetime.now()
        stats['duration_seconds'] = (
            stats['completed_at'] - stats['started_at']
        ).total_seconds()

        logger.info(
            f"Collection completed: {stats['articles_saved']} articles saved, "
            f"{stats['articles_skipped']} skipped, "
            f"{stats['urls_discovered']} URLs discovered"
        )

        return stats

    async def _initialize_sources(
        self,
        sources: list[dict[str, Any]],
        session: AsyncSession,
    ) -> int:
        """
        初始化所有源
        检查 robots.txt 和 sitemap

        Args:
            sources: 源列表
            session: 数据库会话

        Returns:
            成功初始化的源数量
        """
        initialized = 0
        site_discovery = SiteDiscovery(session, self.robots_handler)

        for source_dict in sources:
            source_id = source_dict['id']
            try:
                result = await site_discovery.initialize_source(source_id)
                if result.get('success'):
                    initialized += 1
                    logger.info(
                        f"Initialized source {source_id}: "
                        f"robots={result.get('robots_status')}, "
                        f"sitemap={result.get('sitemap_url')}"
                    )
            except Exception as e:
                logger.error(f"Failed to initialize source {source_id}: {e}")

        await site_discovery.close()
        return initialized

    async def _process_source(
        self,
        source_dict: dict[str, Any],
        article_repo: ArticleRepository,
        source_repo: SourceRepository,
    ) -> dict[str, Any]:
        """
        处理单个爬虫源

        Args:
            source_dict: 爬虫源数据字典
            article_repo: 文章仓库
            source_repo: 爬虫源仓库

        Returns:
            处理结果统计
        """
        stats = {
            'source_id': source_dict['id'],
            'site_name': source_dict['site_name'],
            'urls_discovered': 0,
            'articles_crawled': 0,
            'articles_saved': 0,
            'articles_skipped': 0,
            'robots_denied': 0,
            'discovery_method': source_dict.get('discovery_method', 'sitemap'),
        }

        try:
            # 转换为领域模型
            source = source_repo.to_domain_model(source_dict)

            logger.info(f"Processing source: {source.site_name}")

            # 检查 Robots 权限
            if self.respect_robots:
                can_fetch = self.robots_handler.can_fetch(
                    source.base_url + '/',
                    source.base_url,
                )
                if not can_fetch:
                    logger.warning(f"Robots.txt denies access to {source.site_name}")
                    stats['robots_denied'] = 1
                    await self._update_source_stats(source_dict['id'], success=False, error="Robots.txt denied")
                    return stats

            # 获取爬取延迟
            crawl_delay = source_dict.get('crawl_delay') or CollectorConfig.DEFAULT_CRAWL_DELAY

            async with UniversalScraper() as scraper:
                # 根据发现策略选择方法
                urls = []
                discovery_method = source_dict.get('discovery_method', 'sitemap')

                if discovery_method in ['sitemap', 'hybrid']:
                    # 优先使用 Sitemap
                    sitemap_url = source_dict.get('sitemap_url')
                    if sitemap_url:
                        urls = await self._discover_from_sitemap(
                            sitemap_url,
                            source_dict.get('sitemap_last_fetched'),
                            article_repo,
                        )
                        stats['urls_discovered'] = len(urls)

                # 如果 Sitemap 不可用或方法为 hybrid/list，使用列表页
                if (not urls or discovery_method in ['list', 'hybrid']):
                    list_urls = await scraper.discover_article_urls(
                        source,
                        max_pages=self.max_discover_pages,
                    )
                    # 去重合并
                    url_set = set(urls)
                    url_set.update(list_urls)
                    urls = list(url_set)
                    stats['urls_discovered'] = len(urls)

                logger.info(f"Discovered {len(urls)} URLs from {source.site_name}")

                if not urls:
                    return stats

                # 2. 过滤已存在的 URL
                new_urls = []
                for url in urls:
                    exists = await article_repo.exists_by_url(url)
                    if not exists:
                        # 检查 Robots 权限
                        if self.respect_robots:
                            if not self.robots_handler.can_fetch(url, source.base_url):
                                stats['robots_denied'] += 1
                                continue
                        new_urls.append(url)
                    else:
                        stats['articles_skipped'] += 1

                logger.info(
                    f"{len(new_urls)} new URLs, {stats['articles_skipped']} already exists"
                )

                if not new_urls:
                    return stats

                # 3. 批量爬取文章（应用延迟）
                articles = await self._scrape_with_delay(
                    scraper,
                    new_urls[: self.max_articles_per_source],
                    source,
                    crawl_delay,
                )
                stats['articles_crawled'] = len(articles)

                logger.info(f"Crawled {len(articles)} articles from {source.site_name}")

                # 4. 保存到数据库
                saved_count = 0
                for article in articles:
                    article_id = await article_repo.create(article)
                    if article_id:
                        saved_count += 1

                stats['articles_saved'] = saved_count

                # 更新源统计
                await self._update_source_stats(
                    source_dict['id'],
                    success=True,
                    articles_saved=saved_count,
                )

                logger.info(
                    f"Saved {saved_count} articles from {source.site_name}"
                )

        except Exception as e:
            logger.error(f"Error processing source {source_dict.get('site_name')}: {e}")
            await self._update_source_stats(source_dict['id'], success=False, error=str(e))
            raise

        return stats

    async def _discover_from_sitemap(
        self,
        sitemap_url: str,
        last_fetched: datetime | None,
        article_repo: ArticleRepository,
    ) -> list[str]:
        """
        从 Sitemap 发现 URL

        Args:
            sitemap_url: Sitemap URL
            last_fetched: 上次获取时间
            article_repo: 文章仓库

        Returns:
            URL 列表
        """
        from src.services.sitemap_parser import SitemapParser

        urls = []

        try:
            async with SitemapParser() as parser:
                entries = await parser.parse_recursive(
                    sitemap_url,
                    last_crawled_at=last_fetched,
                )
                urls = [e.loc for e in entries]

        except Exception as e:
            logger.error(f"Error parsing sitemap: {e}")

        return urls

    async def _scrape_with_delay(
        self,
        scraper: UniversalScraper,
        urls: list[str],
        source: Any,
        delay: float,
    ) -> list[ArticleCreate]:
        """
        带延迟的爬取

        Args:
            scraper: 爬虫实例
            urls: URL 列表
            source: 爬虫源
            delay: 延迟秒数

        Returns:
            文章列表
        """
        articles = []

        for url in urls:
            try:
                article = await scraper.scrape_article(url, source)
                if article:
                    articles.append(article)

                # 应用延迟
                if delay > 0:
                    await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")

        return articles

    async def _update_source_stats(
        self,
        source_id: int,
        success: bool,
        articles_saved: int = 0,
        error: str | None = None,
    ) -> None:
        """
        更新源统计信息

        Args:
            source_id: 源 ID
            success: 是否成功
            articles_saved: 保存的文章数量
            error: 错误信息
        """
        sql = """
            UPDATE crawl_sources
            SET last_crawled_at = :now,
                success_count = success_count + :success_delta,
                failure_count = failure_count + :failure_delta,
                last_error = :error,
                updated_at = :now
            WHERE id = :id
        """

        params = {
            'id': source_id,
            'now': datetime.now(),
            'success_delta': 1 if success else 0,
            'failure_delta': 0 if success else 1,
            'error': error,
        }

        # 执行更新
        from src.repository.base import BaseRepository
        base_repo = BaseRepository()
        await base_repo.execute_write(sql, params)

    async def run_by_source(self, source_id: int) -> dict[str, Any]:
        """
        只爬取指定的爬虫源

        Args:
            source_id: 爬虫源 ID

        Returns:
            采集结果统计
        """
        stats = {
            'source_id': source_id,
            'urls_discovered': 0,
            'articles_crawled': 0,
            'articles_saved': 0,
            'articles_skipped': 0,
            'robots_denied': 0,
            'started_at': datetime.now(),
        }

        async with db_manager.session() as session:
            source_repo = SourceRepository(session)
            article_repo = ArticleRepository(session)

            # 获取指定的爬虫源
            source = await source_repo.get_domain_by_id(source_id)
            if not source:
                logger.error(f"Source {source_id} not found")
                return stats

            if not source.enabled:
                logger.warning(f"Source {source_id} is disabled")
                return stats

            # 转换为字典用于处理
            source_dict = await source_repo.get_by_id(source_id)
            assert source_dict is not None

            result = await self._process_source(source_dict, article_repo, source_repo)

            stats.update(result)

        stats['completed_at'] = datetime.now()
        stats['duration_seconds'] = (
            stats['completed_at'] - stats['started_at']
        ).total_seconds()

        return stats

    async def run_by_url(self, url: str, source_id: int) -> dict[str, Any]:
        """
        爬取单个 URL

        Args:
            url: 文章 URL
            source_id: 爬虫源 ID

        Returns:
            采集结果
        """
        stats = {
            'url': url,
            'source_id': source_id,
            'success': False,
            'article_id': None,
            'error': None,
        }

        async with db_manager.session() as session:
            source_repo = SourceRepository(session)
            article_repo = ArticleRepository(session)

            # 检查是否已存在
            exists = await article_repo.exists_by_url(url)
            if exists:
                stats['error'] = 'URL already exists'
                return stats

            # 获取爬虫源配置
            source = await source_repo.get_domain_by_id(source_id)
            if not source:
                stats['error'] = 'Source not found'
                return stats

            try:
                async with UniversalScraper() as scraper:
                    article = await scraper.scrape_article(url, source)

                    if article:
                        article_id = await article_repo.create(article)
                        if article_id:
                            stats['success'] = True
                            stats['article_id'] = article_id
                        else:
                            stats['error'] = 'Failed to save article'
                    else:
                        stats['error'] = 'Failed to scrape article'

            except Exception as e:
                stats['error'] = str(e)
                logger.error(f"Error scraping URL {url}: {e}")

        return stats


# CLI 入口函数
async def main() -> None:
    """主函数入口"""
    # 初始化日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    )

    # 初始化数据库
    await init_db()

    try:
        # 创建调度器
        collector = NewsCollector(
            concurrent_sources=3,
            concurrent_articles=5,
            max_discover_pages=3,
            max_articles_per_source=50,
            respect_robots=True,
        )

        # 执行采集
        stats = await collector.run_once(initialize_sources=True)

        # 打印统计
        print("\n" + "=" * 50)
        print("Collection Summary:")
        print(f"  Sources processed: {stats['sources_processed']}")
        print(f"  Sources initialized: {stats.get('sources_initialized', 0)}")
        print(f"  URLs discovered: {stats['urls_discovered']}")
        print(f"  Articles crawled: {stats['articles_crawled']}")
        print(f"  Articles saved: {stats['articles_saved']}")
        print(f"  Articles skipped: {stats['articles_skipped']}")
        print(f"  Robots denied: {stats.get('robots_denied', 0)}")
        print(f"  Duration: {stats.get('duration_seconds', 0):.2f}s")
        if stats['errors']:
            print(f"  Errors: {len(stats['errors'])}")
        print("=" * 50 + "\n")

    finally:
        # 关闭数据库
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
