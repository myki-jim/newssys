"""
轻量服务监督器

职责：
1. 拉起 API 或 worker 子进程
2. 周期性健康检查
3. 到达最大运行时长后主动退出，让 Docker 按 restart policy 重启
"""

from __future__ import annotations

import asyncio
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    return int(value)


def child_command(role: str) -> list[str]:
    if role == "api":
        host = os.getenv("API_HOST", "0.0.0.0")
        port = os.getenv("API_PORT", "8000")
        return [
            sys.executable,
            "-m",
            "uvicorn",
            "src.api.main:app",
            "--host",
            host,
            "--port",
            port,
        ]

    if role.startswith("worker:") or role == "worker":
        worker_type = role.split(":", 1)[1] if ":" in role else "scheduler"
        return [sys.executable, "-m", f"src.worker.{worker_type}_main"]

    raise ValueError(f"Unknown role: {role}")


def is_api_healthy(url: str, timeout_seconds: int) -> bool:
    try:
        response = httpx.get(url, timeout=timeout_seconds)
        return response.status_code == 200
    except Exception:
        return False


def is_worker_healthy_file(heartbeat_file: str, stale_after_seconds: int) -> bool:
    heartbeat_path = Path(heartbeat_file)
    if not heartbeat_path.exists():
        return False
    age = time.time() - heartbeat_path.stat().st_mtime
    return age <= stale_after_seconds


def _db_health_check_sync(worker_id: str, stale_after_seconds: int) -> bool:
    """同步封装：通过子进程重新导入来检查数据库心跳（避免 asyncio 冲突）"""
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"""
import asyncio
import os, sys
sys.path.insert(0, ".")
os.environ["DATABASE_TYPE"] = os.environ.get("DATABASE_TYPE", "mysql")
os.environ["DATABASE_HOST"] = os.environ.get("DATABASE_HOST", "mysql")
os.environ["DATABASE_PORT"] = os.environ.get("DATABASE_PORT", "3306")
os.environ["DATABASE_USER"] = os.environ.get("DATABASE_USER", "root")
os.environ["DATABASE_PASSWORD"] = os.environ.get("DATABASE_PASSWORD", "")
os.environ["DATABASE_NAME"] = os.environ.get("DATABASE_NAME", "newssys")

async def check():
    from src.core.database import init_engine, close_engine
    from src.repository.worker_heartbeat_repository import WorkerHeartbeatRepository
    from src.core.database import get_async_session
    init_engine()
    async with get_async_session() as db:
        repo = WorkerHeartbeatRepository(db)
        healthy = await repo.is_worker_healthy("{worker_id}", {stale_after_seconds})
    await close_engine()
    return healthy

print("OK" if asyncio.run(check()) else "FAIL")
""",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return "OK" in result.stdout
    except Exception:
        return False


def is_worker_healthy(
    heartbeat_file: str,
    stale_after_seconds: int,
    heartbeat_type: str = "",
    worker_id: str = "",
) -> bool:
    if heartbeat_type == "database" and worker_id:
        return _db_health_check_sync(worker_id, stale_after_seconds)
    return is_worker_healthy_file(heartbeat_file, stale_after_seconds)


def terminate_child(child: subprocess.Popen) -> None:
    if child.poll() is not None:
        return

    child.terminate()
    try:
        child.wait(timeout=20)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=10)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/service_runner.py [api|worker[:<type>]]", file=sys.stderr)
        return 2

    role = sys.argv[1]
    command = child_command(role)
    started_at = time.time()
    max_uptime_seconds = env_int("SERVICE_MAX_UPTIME_SECONDS", 24 * 60 * 60)
    healthcheck_interval_seconds = env_int("SERVICE_HEALTHCHECK_INTERVAL_SECONDS", 30)
    healthcheck_timeout_seconds = env_int("SERVICE_HEALTHCHECK_TIMEOUT_SECONDS", 5)
    healthcheck_grace_seconds = env_int("SERVICE_HEALTHCHECK_GRACE_SECONDS", 60)
    healthcheck_failures = env_int("SERVICE_HEALTHCHECK_FAILURES", 3)
    api_health_url = os.getenv("API_HEALTHCHECK_URL", "http://127.0.0.1:8000/api/v1/health")
    heartbeat_stale_seconds = env_int("SCHEDULER_HEARTBEAT_STALE_SECONDS", 90)
    heartbeat_type = os.getenv("HEARTBEAT_TYPE", "auto")
    worker_id = os.getenv("WORKER_ID", "")
    worker_type = role.split(":", 1)[1] if ":" in role else "scheduler"

    # 按 worker 类型读取对应的心跳文件
    worker_heartbeat_file_map = {
        "scheduler": os.getenv("SCHEDULER_HEARTBEAT_FILE", "/tmp/newssys-scheduler-heartbeat"),
        "crawl": os.getenv("CRAWL_HEARTBEAT_FILE", "/tmp/newssys-crawl-heartbeat"),
        "report": os.getenv("REPORT_HEARTBEAT_FILE", "/tmp/newssys-report-heartbeat"),
        "search": os.getenv("SEARCH_HEARTBEAT_FILE", "/tmp/newssys-search-heartbeat"),
        "ai": os.getenv("AI_HEARTBEAT_FILE", "/tmp/newssys-ai-heartbeat"),
        "sitemap": os.getenv("SITEMAP_HEARTBEAT_FILE", "/tmp/newssys-sitemap-heartbeat"),
    }
    heartbeat_file = worker_heartbeat_file_map.get(
        worker_type, os.getenv("SCHEDULER_HEARTBEAT_FILE", "/tmp/newssys-scheduler-heartbeat")
    )

    # 自动决定心跳类型
    if heartbeat_type == "auto":
        heartbeat_type = "database" if os.getenv("DATABASE_TYPE") == "mysql" else "file"

    # 数据库心跳模式时自动生成 worker_id，并传递给子进程
    if heartbeat_type == "database" and not worker_id:
        worker_id = f"{worker_type}-{socket.gethostname()}-{os.getpid()}"
        os.environ["WORKER_ID"] = worker_id

    child = subprocess.Popen(command)

    def forward_signal(signum, _frame) -> None:
        if child.poll() is None:
            child.send_signal(signum)

    signal.signal(signal.SIGTERM, forward_signal)
    signal.signal(signal.SIGINT, forward_signal)

    consecutive_failures = 0

    while True:
        child_status = child.poll()
        if child_status is not None:
            return child_status

        uptime = time.time() - started_at
        if max_uptime_seconds > 0 and uptime >= max_uptime_seconds:
            print(f"[runner:{role}] max uptime reached, exiting for scheduled restart", flush=True)
            terminate_child(child)
            return 75

        if uptime >= healthcheck_grace_seconds:
            if role == "api":
                healthy = is_api_healthy(api_health_url, healthcheck_timeout_seconds)
            else:
                healthy = is_worker_healthy(
                    heartbeat_file, heartbeat_stale_seconds,
                    heartbeat_type=heartbeat_type, worker_id=worker_id,
                )

            if healthy:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                print(
                    f"[runner:{role}] healthcheck failed {consecutive_failures}/{healthcheck_failures}",
                    flush=True,
                )
                if consecutive_failures >= healthcheck_failures:
                    print(f"[runner:{role}] unhealthy, exiting for docker restart", flush=True)
                    terminate_child(child)
                    return 70

        time.sleep(healthcheck_interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
