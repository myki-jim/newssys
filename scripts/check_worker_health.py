#!/usr/bin/env python3
"""检查 worker heartbeat。"""

import os
import time
from pathlib import Path


def main() -> int:
    heartbeat_file = Path(
        os.getenv("WORKER_HEARTBEAT_FILE")
        or os.getenv("SCHEDULER_HEARTBEAT_FILE", "/tmp/newssys-scheduler-heartbeat")
    )
    stale_seconds = int(
        os.getenv("WORKER_HEARTBEAT_STALE_SECONDS")
        or os.getenv("SCHEDULER_HEARTBEAT_STALE_SECONDS", "90")
    )

    if not heartbeat_file.exists():
        return 1

    age = time.time() - heartbeat_file.stat().st_mtime
    return 0 if age <= stale_seconds else 1


if __name__ == "__main__":
    raise SystemExit(main())
