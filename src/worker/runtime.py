"""
worker 运行时辅助
提供独立 worker 的启动、停止和 heartbeat 管理。
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from collections.abc import Awaitable, Callable
from pathlib import Path

from src.core.config import settings
from src.core.database import close_engine, get_async_session, init_database
from src.core.worker_logging import init_worker_logging
from src.repository.worker_heartbeat_repository import WorkerHeartbeatRepository

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


async def db_heartbeat_loop(
    worker_id: str,
    worker_type: str,
    stop_event: asyncio.Event,
    interval_seconds: int,
) -> None:
    """周期性写入数据库心跳。"""
    hostname = socket.gethostname()
    pid = os.getpid()

    while not stop_event.is_set():
        try:
            async with get_async_session() as db:
                repo = WorkerHeartbeatRepository(db)
                await repo.upsert_heartbeat(worker_id, worker_type, hostname, pid)
        except Exception:
            logger.exception("数据库心跳写入失败")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


def _resolve_heartbeat_type() -> str:
    """根据配置和数据库类型决定心跳方式"""
    hb_type = settings.runtime.heartbeat_type
    if hb_type == "auto":
        return "database" if settings.database.is_mysql else "file"
    return hb_type


def _generate_worker_id(worker_type: str) -> str:
    """生成 Worker 实例唯一标识"""
    if settings.runtime.worker_id:
        return settings.runtime.worker_id
    hostname = socket.gethostname()
    pid = os.getpid()
    return f"{worker_type}-{hostname}-{pid}"


async def run_worker_process(
    worker_name: str,
    heartbeat_file: str,
    heartbeat_interval_seconds: int,
    workers: list[tuple[str, Callable[[], Awaitable[None]]]],
    stop_hooks: list[Callable[[], Awaitable[None]]] | None = None,
    worker_type: str = "",
) -> None:
    """
    运行独立 worker 进程。
    """
    init_worker_logging()
    logger.info("启动 %s", worker_name)

    await init_database()
    stop_event = asyncio.Event()

    hb_type = _resolve_heartbeat_type()
    worker_id = _generate_worker_id(worker_type or worker_name)

    # 始终运行文件心跳（供 Docker 本地健康检查使用）
    file_heartbeat_task = asyncio.create_task(
        heartbeat_loop(heartbeat_file, stop_event, heartbeat_interval_seconds)
    )

    if hb_type == "database":
        logger.info("%s 使用数据库心跳 (worker_id=%s)", worker_name, worker_id)
        db_heartbeat_task = asyncio.create_task(
            db_heartbeat_loop(worker_id, worker_type or worker_name, stop_event, heartbeat_interval_seconds)
        )
    else:
        logger.info("%s 使用文件心跳: %s", worker_name, heartbeat_file)
        db_heartbeat_task = None

    worker_tasks = [asyncio.create_task(worker()) for _, worker in workers]

    try:
        await asyncio.gather(*worker_tasks)
    finally:
        stop_event.set()
        file_heartbeat_task.cancel()
        if db_heartbeat_task is not None:
            db_heartbeat_task.cancel()
        for task in worker_tasks:
            task.cancel()

        try:
            await file_heartbeat_task
        except asyncio.CancelledError:
            pass
        if db_heartbeat_task is not None:
            try:
                await db_heartbeat_task
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
