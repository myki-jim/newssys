"""
定时任务调度器
负责定期检查并执行到期的定时任务
"""

import asyncio
import logging
from datetime import datetime

from src.core.database import get_async_session
from src.repository.schedule_repository import ScheduleRepository
from src.services.schedule_executor import ScheduleExecutor

logger = logging.getLogger(__name__)


class SchedulerService:
    """调度器服务"""

    def __init__(self, check_interval: int = 60):
        """
        初始化调度器

        Args:
            check_interval: 检查间隔（秒），默认60秒
        """
        self.check_interval = check_interval
        self.running = False
        self.task: asyncio.Task | None = None
        self.executor = ScheduleExecutor()

    async def start(self):
        """启动调度器"""
        if self.running:
            logger.warning("调度器已在运行")
            return

        self.running = True
        logger.info(f"调度器启动，检查间隔: {self.check_interval}秒")

        # 直接运行，不使用 create_task
        while self.running:
            try:
                await self._check_and_run_due_tasks()
            except Exception as e:
                logger.error(f"调度器执行出错: {e}", exc_info=True)

            await asyncio.sleep(self.check_interval)

    async def stop(self):
        """停止调度器"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("调度器已停止")

    async def _check_and_run_due_tasks(self):
        """检查并执行到期的任务"""
        async with get_async_session() as db:
            repo = ScheduleRepository(db)

            # 获取到期的任务
            due_schedules = await repo.get_due_schedules()

            if not due_schedules:
                logger.debug("没有到期任务")
                return

            logger.info(f"发现 {len(due_schedules)} 个到期任务")

            # 创建任务记录
            from src.repository.task_repository import TaskRepository
            from sqlalchemy import text
            import json

            task_repo = TaskRepository(db)

            for schedule in due_schedules:
                try:
                    # 创建执行任务记录（直接插入，跳过 TaskType 验证）
                    result = await db.execute(
                        text("""
                            INSERT INTO tasks (task_type, status, title, params, progress_current, progress_total, created_at, updated_at)
                            VALUES (:task_type, :status, :title, :params, 0, 0, :created_at, :updated_at)
                            RETURNING id
                        """),
                        {
                            "task_type": f"schedule_{schedule['schedule_type']}",
                            "status": "pending",
                            "title": f"执行定时任务: {schedule['name']}",
                            "params": json.dumps({"schedule_id": schedule["id"]}),
                            "created_at": datetime.now(),
                            "updated_at": datetime.now(),
                        }
                    )
                    row = result.fetchone()
                    task_id = row[0] if row else None
                    await db.commit()

                    # 执行任务（同步执行，避免并发问题）
                    await self.executor.execute_schedule(schedule["id"], task_id)

                    # 计算并更新下次运行时间
                    from datetime import timedelta
                    interval = schedule.get("interval_minutes", 60)
                    next_run = datetime.now() + timedelta(minutes=interval)
                    await repo.update_next_run(schedule["id"], next_run)

                    logger.info(
                        f"任务 {schedule['name']} (ID: {schedule['id']}) 执行完成，下次运行: {next_run}"
                    )

                except Exception as e:
                    logger.error(
                        f"执行任务 {schedule['name']} 失败: {e}", exc_info=True
                    )


# 全局调度器实例
_scheduler_task: asyncio.Task | None = None


def get_scheduler() -> SchedulerService:
    """获取调度器单例（用于状态查询）"""
    return SchedulerService(check_interval=60)


async def start_scheduler():
    """启动调度器（用于应用启动时调用）"""
    global _scheduler_task
    if _scheduler_task is not None:
        logger.warning("调度器任务已存在")
        return

    async def run_scheduler():
        scheduler = SchedulerService(check_interval=60)
        try:
            await scheduler.start()
        except asyncio.CancelledError:
            logger.info("调度器任务被取消")
            raise

    _scheduler_task = asyncio.create_task(run_scheduler())
    logger.info("调度器后台任务已创建")


async def stop_scheduler():
    """停止调度器（用于应用关闭时调用）"""
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        _scheduler_task = None
        logger.info("调度器后台任务已停止")
