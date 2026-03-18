"""
兼容入口
默认启动调度 worker，避免旧脚本直接失效。
"""

from src.worker.scheduler_main import main


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
