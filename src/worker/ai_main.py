"""
AI 对话 worker 入口
只消费 AI 对话任务。
"""

from __future__ import annotations

from src.core.config import settings
from src.core.models import TaskType
from src.services import task_executors  # noqa: F401
from src.services.task_worker_service import TaskWorkerService
from src.worker.runtime import run_worker_process


async def main() -> None:
    task_worker = TaskWorkerService(
        task_types=[TaskType.AI_CHAT.value],
        worker_name="AI 对话 worker",
    )
    await run_worker_process(
        worker_name="AI 对话 worker",
        heartbeat_file=settings.runtime.ai_heartbeat_file,
        heartbeat_interval_seconds=settings.runtime.scheduler_heartbeat_interval_seconds,
        workers=[("ai-task-worker", task_worker.run_forever)],
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
