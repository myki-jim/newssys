"""
Task Repository 模块
负责任务数据的持久化操作
"""

import json
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import (
    Task,
    TaskCreate,
    TaskEventType,
    TaskStatus,
    TaskUpdate,
)
from src.repository.base import BaseRepository


class TaskRepository(BaseRepository):
    """
    Task 数据访问层
    处理任务的存储、查询和更新
    """

    TABLE_NAME = "tasks"
    EVENTS_TABLE_NAME = "task_events"

    def __init__(self, session: AsyncSession | None = None) -> None:
        """初始化 TaskRepository"""
        super().__init__(session)

    async def create(self, task: TaskCreate) -> int:
        """
        创建新任务

        Args:
            task: 任务创建数据

        Returns:
            新插入的任务 ID
        """
        data = {
            "task_type": task.task_type.value,
            "status": TaskStatus.PENDING.value,
            "title": task.title,
            "params": json.dumps(task.params) if task.params else None,
            "progress_current": 0,
            "progress_total": 0,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        return await self.insert(self.TABLE_NAME, data, returning="id")

    async def get_by_id(self, task_id: int) -> dict[str, Any] | None:
        """
        根据 ID 获取任务

        Args:
            task_id: 任务 ID

        Returns:
            任务数据字典
        """
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE id = :id"
        row = await self.fetch_one(sql, {"id": task_id})

        if row:
            return self._parse_task_row(dict(row))
        return None

    async def list_tasks(
        self,
        status: TaskStatus | None = None,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        获取任务列表

        Args:
            status: 任务状态过滤
            task_type: 任务类型过滤
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            任务列表
        """
        conditions = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if status:
            conditions.append("status = :status")
            params["status"] = status.value

        if task_type:
            conditions.append("task_type = :task_type")
            params["task_type"] = task_type

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        sql = f"""
            SELECT * FROM {self.TABLE_NAME}
            {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """

        rows = await self.fetch_all(sql, params)
        return [self._parse_task_row(dict(row)) for row in rows]

    async def get_running_tasks(self, task_type: str | None = None) -> list[dict[str, Any]]:
        """
        获取正在运行的任务

        Args:
            task_type: 任务类型过滤（可选）

        Returns:
            运行中的任务列表
        """
        conditions = ["status = :status"]
        params: dict[str, Any] = {"status": TaskStatus.RUNNING.value}

        if task_type:
            conditions.append("task_type = :task_type")
            params["task_type"] = task_type

        sql = f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at ASC
        """

        rows = await self.fetch_all(sql, params)
        return [self._parse_task_row(dict(row)) for row in rows]

    async def update_status(
        self,
        task_id: int,
        status: TaskStatus,
        error_message: str | None = None,
    ) -> int:
        """
        更新任务状态

        Args:
            task_id: 任务 ID
            status: 新状态
            error_message: 错误信息（可选）

        Returns:
            影响的行数
        """
        data: dict[str, Any] = {
            "status": status.value,
            "updated_at": datetime.now(),
        }

        if status == TaskStatus.RUNNING and "started_at" not in data:
            data["started_at"] = datetime.now()

        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            data["completed_at"] = datetime.now()

        if error_message:
            data["error_message"] = error_message

        return await self.update(
            self.TABLE_NAME, data, "id = :id", {"id": task_id}
        )

    async def update_progress(
        self,
        task_id: int,
        current: int,
        total: int,
        message: str | None = None,
        intermediate_result: dict[str, Any] | None = None,
    ) -> int:
        """
        更新任务进度

        Args:
            task_id: 任务 ID
            current: 当前进度
            total: 总进度
            message: 进度消息（可选）
            intermediate_result: 中间结果（可选），用于实时显示成功/失败/跳过计数

        Returns:
            影响的行数
        """
        data: dict[str, Any] = {
            "progress_current": current,
            "progress_total": total,
            "updated_at": datetime.now(),
        }

        if message:
            # 将消息存储到 error_message 字段（临时显示）
            data["error_message"] = message

        if intermediate_result:
            # 存储中间结果到 result 字段（实时更新）
            data["result"] = json.dumps(intermediate_result, ensure_ascii=False)

        return await self.update(
            self.TABLE_NAME, data, "id = :id", {"id": task_id}
        )

    async def update_result(
        self,
        task_id: int,
        result: dict[str, Any],
    ) -> int:
        """
        更新任务结果

        Args:
            task_id: 任务 ID
            result: 结果数据

        Returns:
            影响的行数
        """
        data: dict[str, Any] = {
            "result": json.dumps(result),
            "updated_at": datetime.now(),
        }

        return await self.update(
            self.TABLE_NAME, data, "id = :id", {"id": task_id}
        )

    async def add_event(
        self,
        task_id: int,
        event_type: TaskEventType,
        event_data: dict[str, Any] | None = None,
    ) -> int:
        """
        添加任务事件

        Args:
            task_id: 任务 ID
            event_type: 事件类型
            event_data: 事件数据

        Returns:
            新插入的事件 ID
        """
        data = {
            "task_id": task_id,
            "event_type": event_type.value,
            "event_data": json.dumps(event_data) if event_data else None,
            "created_at": datetime.now(),
        }

        return await self.insert(self.EVENTS_TABLE_NAME, data, returning="id")

    async def get_events(
        self,
        task_id: int,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        获取任务事件列表

        Args:
            task_id: 任务 ID
            limit: 返回数量限制

        Returns:
            事件列表
        """
        sql = f"""
            SELECT * FROM {self.EVENTS_TABLE_NAME}
            WHERE task_id = :task_id
            ORDER BY created_at ASC
            LIMIT :limit
        """

        rows = await self.fetch_all(sql, {"task_id": task_id, "limit": limit})

        return [
            {
                "id": row["id"],
                "task_id": row["task_id"],
                "event_type": row["event_type"],
                "event_data": json.loads(row["event_data"]) if row["event_data"] else None,
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    async def count_by_status(self, status: TaskStatus) -> int:
        """
        统计指定状态的任务数量

        Args:
            status: 任务状态

        Returns:
            任务数量
        """
        return await self.count(
            self.TABLE_NAME, "status = :status", {"status": status.value}
        )

    async def count_by_type(self, task_type: str) -> int:
        """
        统计指定类型的任务数量

        Args:
            task_type: 任务类型

        Returns:
            任务数量
        """
        return await self.count(
            self.TABLE_NAME, "task_type = :task_type", {"task_type": task_type}
        )

    def _parse_task_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """
        解析任务行数据

        Args:
            row: 数据库行数据

        Returns:
            解析后的任务数据
        """
        # 解析 result 字段 - 可能是 JSON 字符串或 NULL
        result = None
        if row.get("result"):
            try:
                result = json.loads(row["result"])
            except (json.JSONDecodeError, TypeError):
                # 如果解析失败，保持原样或设为 None
                result = row.get("result")

        return {
            "id": row["id"],
            "task_type": row["task_type"],
            "status": row["status"],
            "title": row["title"],
            "params": json.loads(row["params"]) if row.get("params") else {},
            "result": result,
            "progress_current": row.get("progress_current", 0),
            "progress_total": row.get("progress_total", 0),
            "error_message": row.get("error_message"),
            "started_at": row.get("started_at"),
            "completed_at": row.get("completed_at"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
