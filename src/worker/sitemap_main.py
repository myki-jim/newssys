"""
Sitemap 同步 worker 入口
只消费 sitemap_sync 任务，与爬取 worker 隔离避免饥饿。
"""

from __future__ import annotations

from src.core.config import settings
from src.core.models import TaskType
from src.services import task_executors  # noqa: F401
from src.services.task_worker_service import TaskWorkerService
from src.worker.runtime import run_worker_process


async def main() -> None:
    task_worker = TaskWorkerService(
        task_types=[
            TaskType.SITEMAP_SYNC.value,
        ],
        worker_name="Sitemap 同步 worker",
    )
    await run_worker_process(
        worker_name="Sitemap 同步 worker",
        heartbeat_file=settings.runtime.sitemap_heartbeat_file,
        heartbeat_interval_seconds=settings.runtime.scheduler_heartbeat_interval_seconds,
        workers=[("sitemap-task-worker", task_worker.run_forever)],
        worker_type="sitemap",
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
