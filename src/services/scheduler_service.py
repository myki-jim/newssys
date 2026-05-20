"""
定时任务调度器
负责定期检查并执行到期的定时任务
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta

from sqlalchemy import text

from src.core.database import get_async_session
from src.core.models import TaskType
from src.repository.schedule_repository import ScheduleRepository
from src.repository.source_repository import SourceRepository
from src.repository.task_repository import TaskRepository
from src.core.models import TaskEventType, TaskStatus
from src.services.task_manager import TaskManager
from src.services.schedule_executor import ScheduleExecutor

logger = logging.getLogger(__name__)


class SchedulerService:
    """调度器服务"""

    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval
        self.running = False
        self.task: asyncio.Task | None = None
        self.last_check_at: datetime | None = None
        self.last_error: str | None = None

    async def run_forever(self) -> None:
        """持续运行调度器，直到被取消。"""
        if self.running:
            logger.warning("调度器已在运行")
            return

        self.running = True
        logger.info("调度器启动，检查间隔: %s秒", self.check_interval)

        try:
            while self.running:
                self.last_check_at = datetime.now()
                try:
                    await self._check_and_run_due_tasks()
                    self.last_error = None
                except Exception as exc:
                    self.last_error = str(exc)
                    logger.error("调度器执行出错: %s", exc, exc_info=True)

                await asyncio.sleep(self.check_interval)
        except asyncio.CancelledError:
            logger.info("调度器任务被取消")
            raise
        finally:
            self.running = False

    async def stop(self) -> None:
        """停止调度器。"""
        self.running = False
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            finally:
                self.task = None
        logger.info("调度器已停止")

    async def trigger_once(self) -> int:
        """手动触发一次调度检查。"""
        return await self._check_and_run_due_tasks()

    async def dispatch_schedule_by_id(self, schedule_id: int) -> dict:
        """按 ID 手动派发单个定时任务。"""
        async with get_async_session() as db:
            repo = ScheduleRepository(db)
            schedule = await repo.get_by_id(schedule_id)

        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")

        if schedule["status"] != "active":
            raise ValueError("任务未激活，无法执行")

        task_id = await self._create_schedule_task(schedule)
        try:
            if task_id is not None:
                await self._mark_task_running(task_id)
            result = await self._dispatch_schedule(schedule)
            await self._mark_next_run(schedule)
            if task_id is not None:
                await self._mark_task_completed(
                    task_id,
                    {"schedule_id": schedule["id"], **result},
                )
            return result
        except Exception as exc:
            if task_id is not None:
                await self._mark_task_failed(task_id, str(exc))
            raise

    async def _check_and_run_due_tasks(self) -> int:
        """检查并执行到期任务（含 Leader 选举）。"""
        from src.repository.base import BaseRepository

        # 获取 Leader 锁，持有到全部到期任务处理完毕
        async with get_async_session() as lock_db:
            base_repo = BaseRepository(lock_db)
            acquired = await base_repo.acquire_advisory_lock("newssys_scheduler_leader", 5)
            if not acquired:
                logger.debug("未获取调度器 Leader 锁，跳过本轮")
                return 0

            repo = ScheduleRepository(lock_db)
            due_schedules = await repo.get_due_schedules()

            if not due_schedules:
                logger.debug("没有到期任务")
                return 0

            logger.info("发现 %s 个到期任务", len(due_schedules))

            executed = 0
            for schedule in due_schedules:
                task_id = None
                try:
                    task_id = await self._create_schedule_task(schedule)
                    if task_id is not None:
                        await self._mark_task_running(task_id)
                    dispatch_result = await self._dispatch_schedule(schedule)
                    await self._mark_next_run(schedule)
                    if task_id is not None:
                        await self._mark_task_completed(
                            task_id,
                            {"schedule_id": schedule["id"], **dispatch_result},
                        )
                    executed += 1
                    logger.info("任务 %s (ID: %s) 派发完成", schedule["name"], schedule["id"])
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if task_id is not None:
                        await self._mark_task_failed(task_id, str(exc))
                    logger.error("执行任务 %s 失败: %s", schedule["name"], exc, exc_info=True)

        return executed

    async def _dispatch_schedule(self, schedule: dict) -> dict:
        """将调度任务派发到对应 worker。"""
        schedule_type = schedule["schedule_type"]

        if schedule_type == "sitemap_crawl":
            return await self._enqueue_sitemap_sync_tasks(schedule)
        if schedule_type == "article_crawl":
            return await self._enqueue_article_crawl_task(schedule)
        if schedule_type == "keyword_search":
            return await self._enqueue_keyword_search_task(schedule)
        if schedule_type == "cleanup_low_quality":
            return await self._enqueue_cleanup_task(schedule)

        # 暂时保留少数非爬取类旧逻辑，避免直接中断已有配置。
        logger.warning("调度任务 %s 仍使用兼容直执行路径", schedule_type)
        executor = ScheduleExecutor()
        await executor.execute_schedule(schedule["id"], 0)
        return {"dispatch_mode": "inline_compat", "schedule_type": schedule_type}

    async def _enqueue_sitemap_sync_tasks(self, schedule: dict) -> dict:
        async with get_async_session() as db:
            source_repo = SourceRepository(db)
            manager = TaskManager(db)
            enabled_sources = await source_repo.fetch_many(filters={"enabled": True}, limit=1000)

            created_task_ids: list[int] = []
            for source in enabled_sources:
                task = await manager.create_task(
                    task_type=TaskType.SITEMAP_SYNC,
                    title=f"Sitemap 同步: {source['site_name']}",
                    params={"source_id": source["id"], "schedule_id": schedule["id"]},
                    auto_start=False,
                )
                created_task_ids.append(task.id)

        logger.info("已为调度任务 %s 派发 %s 个 Sitemap 同步任务", schedule["name"], len(created_task_ids))
        return {
            "dispatch_mode": "queue",
            "schedule_type": schedule["schedule_type"],
            "queued_task_count": len(created_task_ids),
            "queued_task_ids": created_task_ids,
        }

    async def _enqueue_article_crawl_task(self, schedule: dict) -> dict:
        config = schedule.get("config") or {}
        limit_per_source = int(config.get("batch_size", 50))

        async with get_async_session() as db:
            manager = TaskManager(db)
            task = await manager.create_task(
                task_type=TaskType.CRAWL_PENDING,
                title=f"定时文章爬取: {schedule['name']}",
                params={"limit_per_source": limit_per_source, "schedule_id": schedule["id"]},
                auto_start=False,
            )

        logger.info("已为调度任务 %s 派发文章爬取任务 %s", schedule["name"], task.id)
        return {
            "dispatch_mode": "queue",
            "schedule_type": schedule["schedule_type"],
            "queued_task_count": 1,
            "queued_task_ids": [task.id],
        }

    async def _enqueue_cleanup_task(self, schedule: dict) -> dict:
        async with get_async_session() as db:
            manager = TaskManager(db)
            task = await manager.create_task(
                task_type=TaskType.CLEANUP_LOW_QUALITY,
                title=f"低质量清理: {schedule['name']}",
                params={"schedule_id": schedule["id"]},
                auto_start=False,
            )

        logger.info("已为调度任务 %s 派发清理任务 %s", schedule["name"], task.id)
        return {
            "dispatch_mode": "queue",
            "schedule_type": schedule["schedule_type"],
            "queued_task_count": 1,
            "queued_task_ids": [task.id],
        }

    async def _enqueue_keyword_search_task(self, schedule: dict) -> dict:
        async with get_async_session() as db:
            manager = TaskManager(db)
            task = await manager.create_task(
                task_type=TaskType.AUTO_SEARCH,
                title=f"关键词搜索: {schedule['name']}",
                params={"schedule_id": schedule["id"]},
                auto_start=False,
            )

        logger.info("已为调度任务 %s 派发关键词搜索任务 %s", schedule["name"], task.id)
        return {
            "dispatch_mode": "queue",
            "schedule_type": schedule["schedule_type"],
            "queued_task_count": 1,
            "queued_task_ids": [task.id],
        }

    async def _create_schedule_task(self, schedule: dict) -> int | None:
        """为计划任务创建对应的任务记录。"""
        from src.core.config import settings

        async with get_async_session() as db:
            insert_sql = text(
                """
                INSERT INTO tasks (
                    task_type, status, title, params,
                    progress_current, progress_total, created_at, updated_at
                )
                VALUES (
                    :task_type, :status, :title, :params,
                    0, 0, :created_at, :updated_at
                )
                """
            )
            params_dict = {
                "task_type": f"schedule_{schedule['schedule_type']}",
                "status": "pending",
                "title": f"执行定时任务: {schedule['name']}",
                "params": json.dumps({"schedule_id": schedule["id"]}),
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
            if settings.database.is_mysql:
                result = await db.execute(insert_sql, params_dict)
                await db.commit()
                return result.lastrowid if result.lastrowid else None
            else:
                result = await db.execute(
                    text(insert_sql.text + " RETURNING id"), params_dict
                )
                row = result.fetchone()
                await db.commit()
                return row[0] if row else None

    async def _mark_next_run(self, schedule: dict) -> None:
        """更新下次执行时间。"""
        interval = schedule.get("interval_minutes", 60)
        next_run = datetime.now() + timedelta(minutes=interval)
        async with get_async_session() as db:
            repo = ScheduleRepository(db)
            await repo.update_next_run(schedule["id"], next_run)

    async def _mark_task_running(self, task_id: int) -> None:
        async with get_async_session() as db:
            repo = TaskRepository(db)
            await repo.update_status(task_id, TaskStatus.RUNNING)
            await repo.add_event(task_id, TaskEventType.STARTED, {"message": "调度任务开始执行"})

    async def _mark_task_completed(self, task_id: int, result: dict) -> None:
        async with get_async_session() as db:
            repo = TaskRepository(db)
            await repo.update_status(task_id, TaskStatus.COMPLETED)
            await repo.update_result(task_id, result)
            await repo.add_event(task_id, TaskEventType.COMPLETED, result)

    async def _mark_task_failed(self, task_id: int, error_message: str) -> None:
        async with get_async_session() as db:
            repo = TaskRepository(db)
            await repo.update_status(task_id, TaskStatus.FAILED, error_message)
            await repo.add_event(task_id, TaskEventType.FAILED, {"error": error_message})


_scheduler_instance: SchedulerService | None = None


def get_scheduler() -> SchedulerService:
    """获取全局调度器实例。"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SchedulerService(check_interval=60)
    return _scheduler_instance


async def start_scheduler() -> None:
    """应用启动时启动调度器。"""
    scheduler = get_scheduler()
    if scheduler.task is not None and not scheduler.task.done():
        logger.warning("调度器任务已存在")
        return

    scheduler.task = asyncio.create_task(scheduler.run_forever())
    logger.info("调度器后台任务已创建")


async def stop_scheduler() -> None:
    """应用关闭时停止调度器。"""
    scheduler = get_scheduler()
    await scheduler.stop()
