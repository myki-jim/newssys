"""
Worker 心跳 Repository
负责 Worker 心跳的数据库持久化操作。
"""

import socket
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.repository.base import BaseRepository


class WorkerHeartbeatRepository(BaseRepository):
    """Worker 心跳数据访问层"""

    TABLE_NAME = "worker_heartbeats"

    def __init__(self, session: AsyncSession | None = None) -> None:
        super().__init__(session)

    async def upsert_heartbeat(
        self,
        worker_id: str,
        worker_type: str,
        hostname: str = "",
        pid: int = 0,
    ) -> None:
        """写入或更新心跳记录"""
        now = datetime.now()
        if settings.database.is_mysql:
            await self.execute_write(
                f"""INSERT INTO {self.TABLE_NAME} (worker_id, worker_type, hostname, pid, last_heartbeat_at, created_at)
                    VALUES (:worker_id, :worker_type, :hostname, :pid, :now, :now)
                    ON DUPLICATE KEY UPDATE
                        worker_type = :worker_type2, hostname = :hostname2,
                        pid = :pid2, last_heartbeat_at = :now2""",
                {
                    "worker_id": worker_id,
                    "worker_type": worker_type,
                    "hostname": hostname or socket.gethostname(),
                    "pid": pid,
                    "now": now,
                    "worker_type2": worker_type,
                    "hostname2": hostname or socket.gethostname(),
                    "pid2": pid,
                    "now2": now,
                },
            )
        else:
            await self.execute_write(
                f"""INSERT OR REPLACE INTO {self.TABLE_NAME}
                    (worker_id, worker_type, hostname, pid, last_heartbeat_at, created_at)
                    VALUES (:worker_id, :worker_type, :hostname, :pid, :now,
                            COALESCE((SELECT created_at FROM {self.TABLE_NAME} WHERE worker_id = :worker_id2), :now2))""",
                {
                    "worker_id": worker_id,
                    "worker_type": worker_type,
                    "hostname": hostname or socket.gethostname(),
                    "pid": pid,
                    "now": now,
                    "worker_id2": worker_id,
                    "now2": now,
                },
            )

    async def get_heartbeat_age(self, worker_id: str) -> float | None:
        """获取指定 Worker 上次心跳距今的秒数，不存在则返回 None"""
        now = datetime.now()
        row = await self.fetch_one(
            f"SELECT last_heartbeat_at FROM {self.TABLE_NAME} WHERE worker_id = :worker_id",
            {"worker_id": worker_id},
        )
        if not row:
            return None
        last_hb: datetime = row["last_heartbeat_at"]
        return (now - last_hb).total_seconds()

    async def get_active_workers(self, stale_seconds: int = 90) -> list[dict[str, Any]]:
        """获取活跃的 Worker 列表"""
        if settings.database.is_mysql:
            sql = f"""
                SELECT * FROM {self.TABLE_NAME}
                WHERE last_heartbeat_at >= DATE_SUB(NOW(), INTERVAL :stale_seconds SECOND)
                ORDER BY worker_type, worker_id
            """
        else:
            sql = f"""
                SELECT * FROM {self.TABLE_NAME}
                WHERE last_heartbeat_at >= datetime('now', :stale_seconds_str || ' seconds')
                ORDER BY worker_type, worker_id
            """
        params = {
            "stale_seconds": stale_seconds,
            "stale_seconds_str": f"-{stale_seconds}",
        }
        rows = await self.fetch_all(sql, params)
        return [dict(row) for row in rows]

    async def cleanup_stale_heartbeats(self, max_age_seconds: int = 300) -> int:
        """清理过期心跳记录"""
        if settings.database.is_mysql:
            sql = f"""
                DELETE FROM {self.TABLE_NAME}
                WHERE last_heartbeat_at < DATE_SUB(NOW(), INTERVAL :max_age SECOND)
            """
        else:
            sql = f"""
                DELETE FROM {self.TABLE_NAME}
                WHERE last_heartbeat_at < datetime('now', :max_age_str || ' seconds')
            """
        params = {
            "max_age": max_age_seconds,
            "max_age_str": f"-{max_age_seconds}",
        }
        return await self.execute_write(sql, params)

    async def is_worker_healthy(self, worker_id: str, stale_seconds: int = 90) -> bool:
        """检查指定 Worker 是否健康"""
        age = await self.get_heartbeat_age(worker_id)
        if age is None:
            return False
        return age <= stale_seconds
