"""
轻量服务监督器

职责：
1. 拉起 API 或 worker 子进程
2. 周期性健康检查
3. 到达最大运行时长后主动退出，让 Docker 按 restart policy 重启
"""

from __future__ import annotations

import os
import signal
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

    if role == "worker":
        return [sys.executable, "-m", "src.worker.main"]

    raise ValueError(f"Unknown role: {role}")


def is_api_healthy(url: str, timeout_seconds: int) -> bool:
    try:
        response = httpx.get(url, timeout=timeout_seconds)
        return response.status_code == 200
    except Exception:
        return False


def is_worker_healthy(heartbeat_file: str, stale_after_seconds: int) -> bool:
    heartbeat_path = Path(heartbeat_file)
    if not heartbeat_path.exists():
        return False
    age = time.time() - heartbeat_path.stat().st_mtime
    return age <= stale_after_seconds


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
    if len(sys.argv) != 2:
        print("usage: python scripts/service_runner.py [api|worker]", file=sys.stderr)
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
    heartbeat_file = os.getenv("SCHEDULER_HEARTBEAT_FILE", "/tmp/newssys-scheduler-heartbeat")
    heartbeat_stale_seconds = env_int("SCHEDULER_HEARTBEAT_STALE_SECONDS", 90)

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
                healthy = is_worker_healthy(heartbeat_file, heartbeat_stale_seconds)

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
