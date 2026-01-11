"""
任务执行器实现
具体的任务执行逻辑
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import (
    FetchStatus,
    PendingArticleStatus,
    TaskEventType,
)
from src.repository.article_repository import ArticleRepository
from src.repository.pending_article_repository import PendingArticleRepository
from src.repository.source_repository import SourceRepository
from src.services.task_manager import TaskExecutor
from src.services.universal_scraper import UniversalScraper


logger = logging.getLogger(__name__)


class CrawlPendingExecutor(TaskExecutor):
    """
    批量爬取待爬文章执行器
    """

    async def execute(
        self,
        task_id: int,
        params: dict[str, Any],
        on_progress: Callable[[int, int, str | None], None] | None = None,
        on_event: Callable[[TaskEventType, dict[str, Any] | None], None] | None = None,
        check_cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """
        执行批量爬取待爬文章任务

        Args:
            task_id: 任务 ID
            params: 任务参数 (limit_per_source: int)
            on_progress: 进度回调
            on_event: 事件回调
            check_cancelled: 取消检查回调

        Returns:
            任务结果
        """
        print(f"[CrawlPendingExecutor] 开始执行任务 {task_id}")
        limit_per_source = params.get("limit_per_source", 10)
        print(f"[CrawlPendingExecutor] limit_per_source={limit_per_source}")

        # 创建新的数据库会话
        from src.core.database import get_async_session

        print(f"[CrawlPendingExecutor] 准备创建数据库会话...")
        async with get_async_session() as db:
            print(f"[CrawlPendingExecutor] 数据库会话已创建")
            pending_repo = PendingArticleRepository(db)
            source_repo = SourceRepository(db)
            article_repo = ArticleRepository(db)

            print(f"[CrawlPendingExecutor] 获取启用的源列表...")
            # 获取所有启用的源
            sources = await source_repo.fetch_many(
                filters={"enabled": True},
                limit=100,
            )

            print(f"[CrawlPendingExecutor] 获取到 {len(sources) if sources else 0} 个启用的源")

            if not sources:
                print(f"[CrawlPendingExecutor] 没有启用的源！")
                return {
                    "success": 0,
                    "failed": 0,
                    "skipped": 0,
                    "sources": [],
                }

            # 计算总数
            total_sources = len(sources)
            print(f"[CrawlPendingExecutor] 总共 {total_sources} 个源")
            result = {
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "sources": [],
            }

            scraper = UniversalScraper()

            for source_index, source in enumerate(sources):
                # 检查取消
                if check_cancelled and check_cancelled():
                    break

                source_name = source["site_name"]
                source_id = source["id"]
                if on_progress:
                    on_progress(
                        source_index,
                        total_sources,
                        f"正在处理源: {source_name}",
                    )

                # 获取该源的待爬文章 - 使用 fetch_all 和原始 SQL
                # 注意：SQLite 的 LIMIT 不支持参数绑定，需要直接嵌入值
                print(f"[CrawlPendingExecutor] 查询源 {source_name} (ID={source_id}) 的待爬文章")

                pending_articles = await pending_repo.fetch_all(
                    f"""SELECT * FROM pending_articles
                    WHERE source_id = :source_id AND status = :status
                    ORDER BY publish_time DESC NULLS LAST, created_at DESC
                    LIMIT {limit_per_source}""",
                    {
                        "source_id": source_id,
                        "status": PendingArticleStatus.PENDING.value,
                    },
                )

                print(f"[CrawlPendingExecutor] 源 {source_name} 查询到 {len(pending_articles) if pending_articles else 0} 条待爬文章")

                if not pending_articles:
                    result["skipped"] += 1
                    # 更新进度（包含中间结果）
                    if on_progress:
                        on_progress(
                            source_index + 1,
                            total_sources,
                            f"跳过源: {source_name} (无待爬文章)",
                            {"success": result["success"], "failed": result["failed"], "skipped": result["skipped"]},
                        )
                    continue

                source_result = {
                    "source_id": source_id,
                    "site_name": source_name,
                    "success": 0,
                    "failed": 0,
                }

                # 爬取每篇文章
                for article in pending_articles:
                    # 检查取消
                    if check_cancelled and check_cancelled():
                        break

                    try:
                        # 标记为爬取中
                        await pending_repo.update_status(
                            article["id"],
                            PendingArticleStatus.CRAWLING,
                        )

                        # 使用通用爬虫爬取
                        scraped = await scraper.scrape(
                            url=article["url"],
                            source_id=source_id,
                            parser_config=source["parser_config"],
                        )

                        # 保存文章到 articles 表
                        await article_repo.create_from_scraped(scraped, source_id)

                        # 标记待爬文章为已完成
                        await pending_repo.update_status(
                            article["id"],
                            PendingArticleStatus.COMPLETED,
                        )

                        source_result["success"] += 1
                        result["success"] += 1

                    except Exception as e:
                        logger.error(f"Failed to crawl article {article['url']}: {e}")

                        # 标记为失败
                        await pending_repo.update_status(
                            article["id"],
                            PendingArticleStatus.FAILED,
                        )

                        source_result["failed"] += 1
                        result["failed"] += 1

                result["sources"].append(source_result)

                # 处理完源后更新进度（包含中间结果）
                if on_progress:
                    on_progress(
                        source_index + 1,
                        total_sources,
                        f"已完成: {source_name}",
                        {"success": result["success"], "failed": result["failed"], "skipped": result["skipped"]},
                    )

            return result


class RetryFailedExecutor(TaskExecutor):
    """
    批量重试失败文章执行器
    """

    async def execute(
        self,
        task_id: int,
        params: dict[str, Any],
        on_progress: Callable[[int, int, str | None], None] | None = None,
        on_event: Callable[[TaskEventType, dict[str, Any] | None], None] | None = None,
        check_cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """
        执行批量重试失败文章任务

        Args:
            task_id: 任务 ID
            params: 任务参数 (limit: int)
            on_progress: 进度回调
            on_event: 事件回调
            check_cancelled: 取消检查回调

        Returns:
            任务结果
        """
        limit = params.get("limit", 50)

        from src.core.database import get_async_session

        async with get_async_session() as db:
            article_repo = ArticleRepository(db)
            pending_repo = PendingArticleRepository(db)
            source_repo = SourceRepository(db)

            # 获取失败的待爬文章 - 使用 fetch_all 和原始 SQL
            # 注意：SQLite 的 LIMIT 不支持参数绑定，需要直接嵌入值
            print(f"[RetryFailedExecutor] 查询失败文章，status={PendingArticleStatus.FAILED.value}")
            failed_articles = await pending_repo.fetch_all(
                f"""SELECT * FROM pending_articles
                WHERE status = :status
                ORDER BY created_at DESC
                LIMIT {limit}""",
                {
                    "status": PendingArticleStatus.FAILED.value,
                },
            )
            print(f"[RetryFailedExecutor] 查询到 {len(failed_articles) if failed_articles else 0} 条失败文章")

            if not failed_articles:
                return {
                    "success": 0,
                    "failed": 0,
                    "total": 0,
                }

            total = len(failed_articles)
            result = {
                "success": 0,
                "failed": 0,
                "total": total,
            }

            scraper = UniversalScraper()

            for index, article in enumerate(failed_articles):
                # 检查取消
                if check_cancelled and check_cancelled():
                    break

                # 显示文章URL用于识别
                display_title = article.get("title") or article.get("url", "无标题")
                if len(display_title) > 50:
                    display_title = display_title[:47] + "..."

                if on_progress:
                    on_progress(
                        index,
                        total,
                        f"正在重试: {display_title}",
                    )

                try:
                    # 获取源配置
                    source = await source_repo.fetch_by_id(article["source_id"])
                    if not source:
                        raise Exception(f"源 {article['source_id']} 不存在")

                    # 重新爬取
                    scraped = await scraper.scrape(
                        url=article["url"],
                        source_id=source["id"],
                        parser_config=source["parser_config"],
                    )

                    # 保存文章到 articles 表
                    await article_repo.create_from_scraped(scraped, source["id"])

                    # 标记待爬文章为已完成
                    await pending_repo.update_status(
                        article["id"],
                        PendingArticleStatus.COMPLETED,
                    )

                    result["success"] += 1

                except Exception as e:
                    logger.error(f"Failed to retry article {article['url']}: {e}")

                    # 重试失败，标记为遗弃（ABANDONED）避免无限重试
                    await pending_repo.update_status(
                        article["id"],
                        PendingArticleStatus.ABANDONED,
                    )

                    result["failed"] += 1

                # 每处理完一篇文章后更新进度（包含中间结果）
                if on_progress:
                    on_progress(
                        index + 1,
                        total,
                        f"已完成: {display_title}",
                        {"success": result["success"], "failed": result["failed"], "total": total},
                    )

            if on_progress:
                on_progress(total, total, "完成", {"success": result["success"], "failed": result["failed"], "total": total})

            return result


class SitemapSyncExecutor(TaskExecutor):
    """
    Sitemap 同步执行器
    """

    async def execute(
        self,
        task_id: int,
        params: dict[str, Any],
        on_progress: Callable[[int, int, str | None], None] | None = None,
        on_event: Callable[[TaskEventType, dict[str, Any] | None], None] | None = None,
        check_cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """
        执行 Sitemap 同步任务

        Args:
            task_id: 任务 ID
            params: 任务参数 (source_id: int)
            on_progress: 进度回调
            on_event: 事件回调
            check_cancelled: 取消检查回调

        Returns:
            任务结果
        """
        source_id = params.get("source_id")

        from src.core.database import get_async_session

        async with get_async_session() as db:
            from src.services.sitemap_service import SitemapService

            service = SitemapService(db)

            try:
                if on_event:
                    on_event(
                        TaskEventType.STARTED,
                        {"message": f"开始同步源 {source_id} 的 Sitemap"},
                    )

                if on_progress:
                    on_progress(0, 100, "正在获取 Sitemap")

                result = await service.sync_source_sitemaps(source_id)

                if on_progress:
                    on_progress(100, 100, "完成")

                return result

            finally:
                await service.close()


class CleanupLowQualityExecutor(TaskExecutor):
    """
    清理低质量内容执行器
    同时清理 articles 表和 pending_articles 表中的低质量数据
    """

    async def execute(
        self,
        task_id: int,
        params: dict[str, Any],
        on_progress: Callable[[int, int, str | None], None] | None = None,
        on_event: Callable[[TaskEventType, dict[str, Any] | None], None] | None = None,
        check_cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """
        执行清理低质量内容任务

        Args:
            task_id: 任务 ID
            params: 任务参数 (无额外参数)
            on_progress: 进度回调
            on_event: 事件回调
            check_cancelled: 取消检查回调

        Returns:
            任务结果
        """
        from datetime import timedelta

        print(f"[CleanupLowQualityExecutor] 开始执行任务 {task_id}")

        # 创建新的数据库会话
        from src.core.database import get_async_session

        async with get_async_session() as db:
            article_repo = ArticleRepository(db)
            pending_repo = PendingArticleRepository(db)

            try:
                if on_event:
                    on_event(
                        TaskEventType.STARTED,
                        {"message": "开始清理低质量内容"},
                    )

                if on_progress:
                    on_progress(10, 100, "正在清理文章...")

                # 计算时间阈值
                one_year_ago = datetime.now() - timedelta(days=365)
                one_year_future = datetime.now() + timedelta(days=365)

                # 1. 清理文章
                find_low_quality_sql = """
                    SELECT id FROM articles WHERE
                        status != 'low_quality'
                        AND (
                            LENGTH(COALESCE(content, '')) < 50
                            OR publish_time IS NULL
                            OR publish_time < :one_year_ago
                            OR publish_time > :one_year_future
                        )
                    LIMIT 10000
                """

                articles_to_mark = await article_repo.fetch_all(
                    find_low_quality_sql,
                    {"one_year_ago": one_year_ago, "one_year_future": one_year_future}
                )

                article_marked = 0
                for article in articles_to_mark:
                    await article_repo.update(article["id"], {"status": "low_quality"})
                    article_marked += 1

                print(f"[CleanupLowQualityExecutor] 标记了 {article_marked} 篇文章为低质量")

                if on_progress:
                    on_progress(60, 100, f"已标记 {article_marked} 篇文章，正在清理待爬文章...")

                # 2. 清理待爬文章
                find_low_pending_sql = """
                    SELECT id FROM pending_articles WHERE
                        status != 'low_quality'
                        AND (
                            publish_time IS NULL
                            OR publish_time < :one_year_ago
                            OR publish_time > :one_year_future
                        )
                    LIMIT 50000
                """

                pending_to_mark = await pending_repo.fetch_all(
                    find_low_pending_sql,
                    {"one_year_ago": one_year_ago, "one_year_future": one_year_future}
                )

                pending_marked = 0
                for pending in pending_to_mark:
                    await pending_repo.update_status(pending["id"], PendingArticleStatus.LOW_QUALITY)
                    pending_marked += 1

                print(f"[CleanupLowQualityExecutor] 标记了 {pending_marked} 条待爬文章为低质量")

                if on_progress:
                    on_progress(100, 100, "清理完成")

                if on_event:
                    on_event(
                        TaskEventType.COMPLETED,
                        {
                            "message": f"清理完成：标记了 {article_marked} 篇文章和 {pending_marked} 条待爬文章",
                            "article_marked": article_marked,
                            "pending_marked": pending_marked,
                            "total_marked": article_marked + pending_marked,
                        },
                    )

                return {
                    "success": article_marked + pending_marked,
                    "article_marked": article_marked,
                    "pending_marked": pending_marked,
                    "message": f"成功标记 {article_marked} 篇文章和 {pending_marked} 条待爬文章为低质量",
                }

            except Exception as e:
                logger.error(f"[CleanupLowQualityExecutor] 清理失败: {e}", exc_info=True)
                if on_event:
                    on_event(
                        TaskEventType.FAILED,
                        {"message": f"清理失败: {str(e)}"},
                    )
                raise


# 注册执行器
from src.services.task_manager import TaskExecutorRegistry

TaskExecutorRegistry.register("crawl_pending", CrawlPendingExecutor)
TaskExecutorRegistry.register("retry_failed", RetryFailedExecutor)
TaskExecutorRegistry.register("sitemap_sync", SitemapSyncExecutor)
TaskExecutorRegistry.register("cleanup_low_quality", CleanupLowQualityExecutor)
