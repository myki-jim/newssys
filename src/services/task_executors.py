"""
任务执行器实现
具体的任务执行逻辑
"""

import json
import logging
import random
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import (
    FetchStatus,
    PendingArticleStatus,
    Report,
    ReportTemplate,
    ReportStatus,
    TaskEventType,
)
from src.repository.article_repository import ArticleRepository
from src.repository.base import nulls_last_order
from src.repository.conversation_repository import ConversationRepository
from src.repository.pending_article_repository import PendingArticleRepository
from src.repository.report_repository import ReportRepository, ReportTemplateRepository
from src.repository.source_repository import SourceRepository
from src.services.ai_agent import AIAgentService
from src.services.report_agent import ReportGenerationAgent
from src.services.task_manager import TaskExecutor
from src.services.universal_scraper import UniversalScraper


logger = logging.getLogger(__name__)


class ReportGenerationExecutor(TaskExecutor):
    """报告生成执行器。"""

    async def execute(
        self,
        task_id: int,
        params: dict[str, Any],
        on_progress: Callable[[int, int, str | None], None] | None = None,
        on_event: Callable[[TaskEventType, dict[str, Any] | None], None] | None = None,
        check_cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        from src.core.database import get_async_session

        report_id = params["report_id"]

        async with get_async_session() as db:
            report_repo = ReportRepository(db)
            template_repo = ReportTemplateRepository(db)
            def emit(event_type: str, payload: dict[str, Any]) -> None:
                if on_event:
                    on_event(TaskEventType.INFO, {"stream_event": event_type, **payload})

            try:
                report_data = await report_repo.fetch_by_id(report_id)
                if not report_data:
                    raise ValueError(f"报告不存在: {report_id}")

                template = None
                template_id = params.get("template_id") or report_data.get("template_id")
                if template_id:
                    template = await template_repo.fetch_by_id(template_id)
                if template is None:
                    template = await template_repo.fetch_default()

                if template is None:
                    raise ValueError("未找到可用报告模板")

                report = Report(**report_data)
                agent = ReportGenerationAgent(db)
                current_stream_content = {"title": "", "content": ""}
                full_result: dict[str, Any] = {}
                last_state_token: str | None = None

                def on_section_stream(section_title: str, chunk: str) -> None:
                    nonlocal current_stream_content
                    if current_stream_content["title"] != section_title:
                        current_stream_content = {"title": section_title, "content": chunk}
                    else:
                        current_stream_content["content"] += chunk

                    emit(
                        "section_stream",
                        {
                            "report_id": report_id,
                            "section_title": section_title,
                            "chunk": chunk,
                            "accumulated_content": current_stream_content["content"],
                        },
                    )

                async def process_state(state) -> None:
                    nonlocal full_result, last_state_token
                    full_result = state.data or {}
                    token = json.dumps(
                        {
                            "stage": state.stage.value if hasattr(state.stage, "value") else state.stage,
                            "progress": state.progress,
                            "message": state.message,
                            "data": full_result,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    )
                    if token == last_state_token:
                        return
                    last_state_token = token

                    update_data = {
                        "agent_stage": state.stage,
                        "agent_progress": state.progress,
                        "agent_message": state.message,
                        "total_articles": full_result.get("total_articles", report.total_articles),
                        "clustered_articles": full_result.get("clustered_articles", report.clustered_articles),
                        "event_count": full_result.get("event_count", report.event_count),
                    }

                    if "sections" in full_result:
                        update_data["sections"] = full_result["sections"]

                    await report_repo.update(report_id, update_data)

                    if on_progress:
                        on_progress(state.progress, state.total, state.message, full_result)

                    emit(
                        "state",
                        {
                            "report_id": report_id,
                            "stage": state.stage.value if hasattr(state.stage, "value") else state.stage,
                            "progress": state.progress,
                            "total": state.total,
                            "message": state.message,
                            "data": full_result,
                        },
                    )

                async for state in agent.generate_report(
                    report=report,
                    template=ReportTemplate(**template),
                    on_state_update=process_state,
                    on_section_stream=on_section_stream,
                ):
                    if check_cancelled and check_cancelled():
                        raise RuntimeError("报告生成已取消")
                    await process_state(state)

                statistics = full_result.get("statistics", {})
                await report_repo.update(
                    report_id,
                    {
                        "status": ReportStatus.COMPLETED,
                        "content": full_result.get("content", ""),
                        "sections": full_result.get("sections", []),
                        "total_articles": statistics.get("total_articles", 0),
                        "clustered_articles": statistics.get("clustered_articles", 0),
                        "event_count": statistics.get("event_count", 0),
                        "agent_progress": 100,
                        "agent_message": "报告生成完成",
                    },
                )

                result = {
                    "report_id": report_id,
                    "content": full_result.get("content", ""),
                    "sections": full_result.get("sections", []),
                    "statistics": statistics,
                    "events": full_result.get("events", []),
                }
                emit("complete", result)
                return result
            except Exception as exc:
                await report_repo.update(
                    report_id,
                    {
                        "status": ReportStatus.FAILED,
                        "error_message": str(exc),
                        "agent_message": f"报告生成失败: {exc}",
                    },
                )
                emit("error", {"report_id": report_id, "error": str(exc)})
                raise


class CrawlPendingExecutor(TaskExecutor):
    """批量爬取待爬文章执行器。"""

    @staticmethod
    def _normalize_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        if not isinstance(value, datetime):
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _article_priority(self, article: dict[str, Any], picks_for_source: int) -> float:
        """按发布时间优先，同时加入站点公平性和轻微随机扰动。"""
        publish_time = self._normalize_datetime(article.get("publish_time"))
        if publish_time is None:
            recency_score = 0.25
        else:
            age_hours = max((datetime.now(timezone.utc) - publish_time).total_seconds() / 3600, 0)
            if age_hours <= 6:
                recency_score = 1.4
            elif age_hours <= 24:
                recency_score = 1.15
            elif age_hours <= 72:
                recency_score = 0.9
            elif age_hours <= 168:
                recency_score = 0.6
            else:
                recency_score = 0.3

        fairness_penalty = 1 / (1 + picks_for_source * 0.8)
        jitter = random.uniform(0.9, 1.1)
        return recency_score * fairness_penalty * jitter

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
        limit_per_source = params.get("limit_per_source", 10)
        logger.info("开始执行批量爬取任务 %s, limit_per_source=%s", task_id, limit_per_source)

        # 创建新的数据库会话
        from src.core.database import get_async_session

        async with get_async_session() as db:
            pending_repo = PendingArticleRepository(db)
            source_repo = SourceRepository(db)
            article_repo = ArticleRepository(db)

            # 获取所有启用的源
            sources = await source_repo.fetch_many(
                filters={"enabled": True},
                limit=100,
            )

            logger.info("获取到 %s 个启用的源", len(sources) if sources else 0)

            if not sources:
                logger.warning("没有启用的源")
                return {
                    "success": 0,
                    "failed": 0,
                    "skipped": 0,
                    "sources": [],
                }

            random.shuffle(sources)
            total_sources = len(sources)
            logger.info("总共 %s 个源（已打乱顺序）", total_sources)
            result = {
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "sources": [],
            }

            scraper = UniversalScraper()
            source_queues: list[dict[str, Any]] = []
            source_results: dict[int, dict[str, Any]] = {}

            for source_index, source in enumerate(sources):
                if check_cancelled and check_cancelled():
                    break

                source_name = source["site_name"]
                source_id = source["id"]
                nulls_order = nulls_last_order("publish_time")
                pending_articles = await pending_repo.fetch_all(
                    f"""SELECT * FROM pending_articles
                    WHERE source_id = :source_id AND status = :status
                    ORDER BY {nulls_order}, created_at DESC
                    LIMIT {limit_per_source}""",
                    {
                        "source_id": source_id,
                        "status": PendingArticleStatus.PENDING.value,
                    },
                )

                logger.info("源 %s 查询到 %s 条待爬文章", source_name, len(pending_articles) if pending_articles else 0)

                source_result = {
                    "source_id": source_id,
                    "site_name": source_name,
                    "success": 0,
                    "failed": 0,
                }
                source_results[source_id] = source_result

                if not pending_articles:
                    result["skipped"] += 1
                    if on_progress:
                        on_progress(
                            source_index + 1,
                            total_sources,
                            f"跳过源: {source_name} (无待爬文章)",
                            {"success": result["success"], "failed": result["failed"], "skipped": result["skipped"]},
                        )
                    continue

                source_queues.append(
                    {
                        "source": source,
                        "articles": list(pending_articles),
                        "picked": 0,
                    }
                )

            crawl_plan: list[tuple[dict[str, Any], dict[str, Any]]] = []
            while True:
                available = [entry for entry in source_queues if entry["articles"]]
                if not available:
                    break

                available.sort(
                    key=lambda entry: self._article_priority(entry["articles"][0], entry["picked"]),
                    reverse=True,
                )
                chosen = available[0]
                crawl_plan.append((chosen["source"], chosen["articles"].pop(0)))
                chosen["picked"] += 1

            total_articles = len(crawl_plan)
            logger.info("本轮交错调度后共有 %s 篇待爬文章", total_articles)

            for index, (source, article) in enumerate(crawl_plan):
                if check_cancelled and check_cancelled():
                    break

                source_id = source["id"]
                source_name = source["site_name"]
                source_result = source_results[source_id]
                display_title = article.get("title") or article.get("url", "无标题")
                if len(display_title) > 50:
                    display_title = display_title[:47] + "..."

                if on_progress:
                    on_progress(
                        index,
                        max(total_articles, 1),
                        f"正在爬取: {source_name} / {display_title}",
                        {"success": result["success"], "failed": result["failed"], "skipped": result["skipped"]},
                    )

                try:
                    await pending_repo.update_status(article["id"], PendingArticleStatus.CRAWLING)

                    scraped = await scraper.scrape(
                        url=article["url"],
                        source_id=source_id,
                        parser_config=source["parser_config"],
                    )

                    await article_repo.create_from_scraped(scraped, source_id)
                    await pending_repo.update_status(article["id"], PendingArticleStatus.COMPLETED)

                    source_result["success"] += 1
                    result["success"] += 1
                except Exception as e:
                    logger.error(f"Failed to crawl article {article['url']}: {e}")
                    await pending_repo.update_status(article["id"], PendingArticleStatus.FAILED)
                    source_result["failed"] += 1
                    result["failed"] += 1

                if on_progress:
                    on_progress(
                        index + 1,
                        max(total_articles, 1),
                        f"已完成: {source_name}",
                        {"success": result["success"], "failed": result["failed"], "skipped": result["skipped"]},
                    )

            result["sources"] = list(source_results.values())

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
            logger.info("查询失败文章，status=%s", PendingArticleStatus.FAILED.value)
            failed_articles = await pending_repo.fetch_all(
                f"""SELECT * FROM pending_articles
                WHERE status = :status
                ORDER BY created_at DESC
                LIMIT {limit}""",
                {
                    "status": PendingArticleStatus.FAILED.value,
                },
            )
            logger.info("查询到 %s 条失败文章", len(failed_articles) if failed_articles else 0)

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

        logger.info("开始执行低质量清理任务 %s", task_id)

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

                logger.info("标记了 %s 篇文章为低质量", article_marked)

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

                logger.info("标记了 %s 条待爬文章为低质量", pending_marked)

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


class AutoSearchExecutor(TaskExecutor):
    """
    关键词自动搜索执行器
    """

    async def execute(
        self,
        task_id: int,
        params: dict[str, Any],
        on_progress: Callable[[int, int, str | None], None] | None = None,
        on_event: Callable[[TaskEventType, dict[str, Any] | None], None] | None = None,
        check_cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        from src.core.database import get_async_session
        from src.services.schedule_executor import ScheduleExecutor

        async with get_async_session() as db:
            executor = ScheduleExecutor()

            if on_event:
                on_event(TaskEventType.STARTED, {"message": "开始执行关键词自动搜索"})
            if on_progress:
                on_progress(0, 100, "正在搜索关键词")

            await executor._execute_keyword_search(db, {"config": params})

            if on_progress:
                on_progress(100, 100, "关键词搜索完成")
            if on_event:
                on_event(TaskEventType.COMPLETED, {"message": "关键词搜索完成"})

            return {
                "schedule_id": params.get("schedule_id"),
                "message": "关键词搜索完成",
            }


class AIChatExecutor(TaskExecutor):
    """AI 对话执行器。"""

    async def execute(
        self,
        task_id: int,
        params: dict[str, Any],
        on_progress: Callable[[int, int, str | None], None] | None = None,
        on_event: Callable[[TaskEventType, dict[str, Any] | None], None] | None = None,
        check_cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        from src.core.database import get_async_session

        _ = task_id
        conversation_id = int(params["conversation_id"])
        message = params["message"]
        mode = params.get("mode", "chat")
        web_search_enabled = bool(params.get("web_search_enabled", False))
        internal_search_enabled = bool(params.get("internal_search_enabled", False))

        async with get_async_session() as db:
            conv_repo = ConversationRepository(db)
            agent = AIAgentService(db)
            full_response = ""
            last_state_token: str | None = None

            if not await conv_repo.fetch_by_id(conversation_id):
                raise ValueError(f"对话不存在: {conversation_id}")

            def emit(event_type: str, payload: dict[str, Any]) -> None:
                if on_event:
                    on_event(TaskEventType.INFO, {"stream_event": event_type, **payload})

            def process_state(state) -> None:
                nonlocal last_state_token
                payload = {
                    "conversation_id": conversation_id,
                    "stage": state.stage,
                    "keywords": state.keywords or [],
                    "internal_results": state.internal_results or [],
                    "web_results": state.web_results or [],
                    "progress": state.progress,
                    "total": state.total,
                    "message": state.message,
                }
                token = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
                if token == last_state_token:
                    return
                last_state_token = token
                if on_progress:
                    on_progress(state.progress, state.total, state.message)
                emit("state", payload)

            async for chunk in agent.chat(
                conversation_id=conversation_id,
                message=message,
                mode=mode,
                web_search_enabled=web_search_enabled,
                internal_search_enabled=internal_search_enabled,
                on_state_update=process_state,
                persist_user_message=False,
            ):
                if check_cancelled and check_cancelled():
                    raise RuntimeError("AI 对话已取消")
                full_response += chunk
                emit("chunk", {"conversation_id": conversation_id, "text": chunk})

            emit("end", {"conversation_id": conversation_id, "full_response": full_response})
            return {
                "conversation_id": conversation_id,
                "full_response": full_response,
                "mode": mode,
                "web_search_enabled": web_search_enabled,
                "internal_search_enabled": internal_search_enabled,
            }


# 注册执行器
from src.services.task_manager import TaskExecutorRegistry

TaskExecutorRegistry.register("crawl_pending", CrawlPendingExecutor)
TaskExecutorRegistry.register("retry_failed", RetryFailedExecutor)
TaskExecutorRegistry.register("sitemap_sync", SitemapSyncExecutor)
TaskExecutorRegistry.register("cleanup_low_quality", CleanupLowQualityExecutor)
TaskExecutorRegistry.register("auto_search", AutoSearchExecutor)
TaskExecutorRegistry.register("generate_report", ReportGenerationExecutor)
TaskExecutorRegistry.register("ai_chat", AIChatExecutor)
