"""
调度 worker 入口
只负责定时任务调度和心跳。
"""

from __future__ import annotations

from src.core.config import settings
from src.services.scheduler_service import get_scheduler
from src.worker.runtime import run_worker_process


async def main() -> None:
    scheduler = get_scheduler()
    await run_worker_process(
        worker_name="调度 worker",
        heartbeat_file=settings.runtime.scheduler_heartbeat_file,
        heartbeat_interval_seconds=settings.runtime.scheduler_heartbeat_interval_seconds,
        workers=[("scheduler", scheduler.run_forever)],
        stop_hooks=[scheduler.stop],
        worker_type="scheduler",
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
