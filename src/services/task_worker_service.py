"""
任务 worker 服务
轮询待执行任务，并在 worker 进程中顺序执行。
"""

import asyncio
import logging
import os
import socket
from collections.abc import Iterable

from src.core.database import get_async_session
from src.repository.task_repository import TaskRepository
from src.services.task_manager import TaskExecutorRegistry, TaskManager

logger = logging.getLogger(__name__)


def _generate_worker_id(worker_name: str) -> str:
    """生成 Worker 实例唯一标识。"""
    hostname = socket.gethostname()
    pid = os.getpid()
    return f"{worker_name}-{hostname}-{pid}"


class TaskWorkerService:
    """后台任务消费器。"""

    def __init__(
        self,
        poll_interval: int = 3,
        task_types: Iterable[str] | None = None,
        worker_name: str = "任务 worker",
        worker_id: str = "",
    ):
        self.poll_interval = poll_interval
        self.task_types = set(task_types or [])
        self.worker_name = worker_name
        self.worker_id = worker_id or _generate_worker_id(worker_name)
        self.running = False

    async def run_forever(self) -> None:
        """持续轮询并执行待处理任务。"""
        if self.running:
            logger.warning("%s 已在运行", self.worker_name)
            return

        self.running = True
        logger.info(
            "%s (%s) 启动，轮询间隔: %s秒，任务类型: %s",
            self.worker_name,
            self.worker_id,
            self.poll_interval,
            sorted(self.task_types) if self.task_types else "全部已注册类型",
        )

        try:
            while self.running:
                executed = await self.run_once()
                if executed == 0:
                    await asyncio.sleep(self.poll_interval)
        except asyncio.CancelledError:
            logger.info("%s 被取消", self.worker_name)
            raise
        finally:
            self.running = False

    async def run_once(self) -> int:
        """执行一轮任务扫描（原子抢占）。"""
        registered_types = TaskExecutorRegistry.get_registered_types()
        if self.task_types:
            registered_types = [task_type for task_type in registered_types if task_type in self.task_types]
        if not registered_types:
            logger.warning("%s 没有可用任务执行器", self.worker_name)
            return 0

        async with get_async_session() as db:
            repo = TaskRepository(db)
            task = await repo.claim_next_task(self.worker_id, task_types=registered_types)

        if not task:
            return 0

        logger.info("%s 已抢占任务 %s (%s)", self.worker_name, task["id"], task["task_type"])
        await TaskManager.execute_task_in_background(task["id"])
        return 1
