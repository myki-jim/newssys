#!/usr/bin/env python3
"""检查 API 健康状态。"""

import os
import sys

import httpx


def main() -> int:
    url = os.getenv("API_HEALTHCHECK_URL", "http://127.0.0.1:8000/api/v1/health")
    timeout = float(os.getenv("API_HEALTHCHECK_TIMEOUT_SECONDS", "5"))

    try:
        response = httpx.get(url, timeout=timeout)
        return 0 if response.status_code == 200 else 1
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
