"""
搜索 worker 入口
只消费关键词自动搜索任务。
"""

from __future__ import annotations

from src.core.config import settings
from src.core.models import TaskType
from src.services import task_executors  # noqa: F401
from src.services.task_worker_service import TaskWorkerService
from src.worker.runtime import run_worker_process


async def main() -> None:
    task_worker = TaskWorkerService(
        task_types=[TaskType.AUTO_SEARCH.value],
        worker_name="搜索 worker",
    )
    await run_worker_process(
        worker_name="搜索 worker",
        heartbeat_file=settings.runtime.search_heartbeat_file,
        heartbeat_interval_seconds=settings.runtime.scheduler_heartbeat_interval_seconds,
        workers=[("search-task-worker", task_worker.run_forever)],
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
