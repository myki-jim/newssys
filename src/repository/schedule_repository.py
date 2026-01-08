"""
定时任务 Repository
"""

import json
from datetime import datetime
from typing import Any, Dict, List

from src.repository.base import BaseRepository


class ScheduleRepository(BaseRepository):
    """定时任务仓库"""

    async def create(self, schedule: Dict[str, Any]) -> int:
        """创建定时任务"""
        config = schedule.get("config")
        config_json = json.dumps(config) if config else None

        return await self.insert(
            "schedules",
            {
                "name": schedule["name"],
                "description": schedule.get("description"),
                "schedule_type": schedule["schedule_type"],
                "status": schedule.get("status", "active"),
                "interval_minutes": schedule.get("interval_minutes", 60),
                "max_executions": schedule.get("max_executions"),
                "config": config_json,
                "next_run_at": schedule.get("next_run_at"),
            },
            returning="id",
        )

    async def get_by_id(self, schedule_id: int) -> Dict[str, Any] | None:
        """根据ID获取定时任务"""
        result = await self.fetch_one(
            "SELECT * FROM schedules WHERE id = :id", {"id": schedule_id}
        )
        if not result:
            return None
        data = dict(result)
        # 解析 config JSON
        if data.get("config"):
            try:
                data["config"] = json.loads(data["config"])
            except (json.JSONDecodeError, TypeError):
                data["config"] = {}
        else:
            data["config"] = {}
        return data

    async def list(
        self,
        schedule_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """获取定时任务列表"""
        conditions = []
        params = {}

        if schedule_type:
            conditions.append("schedule_type = :schedule_type")
            params["schedule_type"] = schedule_type

        if status:
            conditions.append("status = :status")
            params["status"] = status

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params["limit"] = limit
        params["offset"] = offset

        sql = f"""
            SELECT * FROM schedules
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """
        results = await self.fetch_all(sql, params)
        # 解析每条记录的 config JSON
        parsed_results = []
        for row in results:
            data = dict(row)
            if data.get("config"):
                try:
                    data["config"] = json.loads(data["config"])
                except (json.JSONDecodeError, TypeError):
                    data["config"] = {}
            else:
                data["config"] = {}
            parsed_results.append(data)
        return parsed_results

    async def update(self, schedule_id: int, data: dict[str, Any]) -> bool:
        """更新定时任务"""
        if not data:
            return False

        # 如果有 config 字段，需要转换为 JSON
        update_data = data.copy()
        if "config" in update_data and update_data["config"] is not None:
            update_data["config"] = json.dumps(update_data["config"])

        set_clause = ", ".join(f"{k} = :{k}" for k in update_data.keys())
        update_data["id"] = schedule_id
        sql = f"UPDATE schedules SET {set_clause} WHERE id = :id"

        result = await self.execute_write(sql, update_data)
        return result > 0

    async def delete(self, schedule_id: int) -> bool:
        """删除定时任务"""
        result = await self.execute_write(
            "DELETE FROM schedules WHERE id = :id", {"id": schedule_id}
        )
        return result > 0

    async def get_due_schedules(self) -> List[Dict[str, Any]]:
        """获取到期的定时任务"""
        now = datetime.now().isoformat()
        sql = """
            SELECT * FROM schedules
            WHERE status = 'active'
              AND next_run_at IS NOT NULL
              AND next_run_at <= :now
            ORDER BY next_run_at ASC
        """
        results = await self.fetch_all(sql, {"now": now})
        # 解析每条记录的 config JSON
        parsed_results = []
        for row in results:
            data = dict(row)
            if data.get("config"):
                try:
                    data["config"] = json.loads(data["config"])
                except (json.JSONDecodeError, TypeError):
                    data["config"] = {}
            else:
                data["config"] = {}
            parsed_results.append(data)
        return parsed_results

    async def increment_execution_count(self, schedule_id: int) -> bool:
        """增加执行次数"""
        now = datetime.now().isoformat()
        sql = """
            UPDATE schedules
            SET execution_count = execution_count + 1,
                last_run_at = :now
            WHERE id = :id
        """
        return await self.execute_write(sql, {"now": now, "id": schedule_id}) > 0

    async def update_next_run(self, schedule_id: int, next_run_at: datetime) -> bool:
        """更新下次运行时间"""
        sql = "UPDATE schedules SET next_run_at = :next_run_at WHERE id = :id"
        return await self.execute_write(
            sql, {"next_run_at": next_run_at.isoformat(), "id": schedule_id}
        ) > 0
