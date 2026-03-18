"""
worker 运行时辅助
提供独立 worker 的启动、停止和 heartbeat 管理。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from src.core.database import close_engine, init_database
from src.core.worker_logging import init_worker_logging

logger = logging.getLogger(__name__)


async def heartbeat_loop(heartbeat_file: str, stop_event: asyncio.Event, interval_seconds: int) -> None:
    """周期性写入 heartbeat 文件。"""
    heartbeat_path = Path(heartbeat_file)
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)

    while not stop_event.is_set():
        heartbeat_path.write_text(str(asyncio.get_running_loop().time()), encoding="utf-8")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


async def run_worker_process(
    worker_name: str,
    heartbeat_file: str,
    heartbeat_interval_seconds: int,
    workers: list[tuple[str, Callable[[], Awaitable[None]]]],
    stop_hooks: list[Callable[[], Awaitable[None]]] | None = None,
) -> None:
    """
    运行独立 worker 进程。
    """
    init_worker_logging()
    logger.info("启动 %s", worker_name)

    await init_database()
    stop_event = asyncio.Event()
    heartbeat_task = asyncio.create_task(
        heartbeat_loop(heartbeat_file, stop_event, heartbeat_interval_seconds)
    )
    worker_tasks = [asyncio.create_task(worker()) for _, worker in workers]

    try:
        await asyncio.gather(*worker_tasks)
    finally:
        stop_event.set()
        heartbeat_task.cancel()
        for task in worker_tasks:
            task.cancel()

        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

        for task in worker_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass

        if stop_hooks:
            for stop_hook in stop_hooks:
                await stop_hook()

        await close_engine()
        logger.info("%s 已退出", worker_name)
