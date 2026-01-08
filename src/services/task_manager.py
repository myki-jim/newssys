"""
Task Manager 服务
负责任务的执行、进度跟踪和取消
"""

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import (
    Task,
    TaskCreate,
    TaskEventType,
    TaskStatus,
    TaskType,
)
from src.repository.task_repository import TaskRepository


# ============================================================================
# 执行器注册表（在文件顶部定义，避免循环导入）
# ============================================================================

class TaskExecutorRegistry:
    """
    任务执行器注册表
    全局单例，用于管理所有任务执行器
    """

    _instance: "TaskExecutorRegistry | None" = None
    _executors: dict[str, type["TaskExecutor"]] = {}

    def __new__(cls) -> "TaskExecutorRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, task_type: str, executor_class: type["TaskExecutor"]) -> None:
        """
        注册任务执行器类

        Args:
            task_type: 任务类型
            executor_class: 执行器类
        """
        cls._executors[task_type] = executor_class

    @classmethod
    def create(cls, task_type: str) -> "TaskExecutor | None":
        """
        创建任务执行器实例

        Args:
            task_type: 任务类型

        Returns:
            执行器实例或 None
        """
        executor_class = cls._executors.get(task_type)
        if executor_class:
            return executor_class()
        return None

    @classmethod
    def get_registered_types(cls) -> list[str]:
        """获取所有已注册的任务类型"""
        return list(cls._executors.keys())


# 进度回调类型别名 (支持可选的中间结果参数)
ProgressCallback = Callable[[int, int, str | None, dict[str, Any] | None], None]
# 事件回调类型别名
EventCallback = Callable[[TaskEventType, dict[str, Any] | None], None]


class TaskExecutor:
    """
    任务执行器基类
    所有任务类型都需要实现此接口
    """

    async def execute(
        self,
        task_id: int,
        params: dict[str, Any],
        on_progress: ProgressCallback | None = None,
        on_event: EventCallback | None = None,
        check_cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """
        执行任务

        Args:
            task_id: 任务 ID
            params: 任务参数
            on_progress: 进度回调 (current, total, message, intermediate_result)
            on_event: 事件回调 (event_type, event_data)
            check_cancelled: 检查是否取消的回调

        Returns:
            任务结果字典
        """
        raise NotImplementedError


class TaskManager:
    """
    任务管理器
    负责任务的创建、执行和管理
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        初始化任务管理器

        Args:
            db: 数据库会话
        """
        self.db = db
        self.repo = TaskRepository(db)
        self._executors: dict[str, TaskExecutor] = {}
        self._running_tasks: dict[int, asyncio.Task] = {}
        self._cancel_flags: dict[int, bool] = {}

    def register_executor(self, task_type: str, executor: TaskExecutor) -> None:
        """
        注册任务执行器

        Args:
            task_type: 任务类型
            executor: 任务执行器
        """
        self._executors[task_type] = executor

    async def create_task(
        self,
        task_type: TaskType | str,
        title: str | None = None,
        params: dict[str, Any] | None = None,
        auto_start: bool = False,
    ) -> Task:
        """
        创建新任务

        Args:
            task_type: 任务类型
            title: 任务标题
            params: 任务参数
            auto_start: 是否自动开始执行

        Returns:
            创建的任务
        """
        if isinstance(task_type, str):
            task_type = TaskType(task_type)

        create = TaskCreate(
            task_type=task_type,
            title=title,
            params=params or {},
        )

        task_id = await self.repo.create(create)
        task_dict = await self.repo.get_by_id(task_id)

        if not task_dict:
            raise RuntimeError(f"Failed to create task")

        # 记录创建事件
        await self.repo.add_event(task_id, TaskEventType.CREATED, {"title": title})

        if auto_start:
            # 在后台启动任务
            asyncio.create_task(self._execute_task(task_id))

        return Task(**task_dict)

    async def get_task(self, task_id: int) -> Task | None:
        """
        获取任务

        Args:
            task_id: 任务 ID

        Returns:
            任务对象或 None
        """
        task_dict = await self.repo.get_by_id(task_id)
        if task_dict:
            return Task(**task_dict)
        return None

    async def list_tasks(
        self,
        status: TaskStatus | None = None,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Task]:
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
        task_dicts = await self.repo.list_tasks(status, task_type, limit, offset)
        return [Task(**t) for t in task_dicts]

    async def cancel_task(self, task_id: int) -> bool:
        """
        取消任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功取消
        """
        task = await self.get_task(task_id)
        if not task:
            return False

        # 只有 pending 或 running 状态的任务可以取消
        if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
            return False

        # 设置取消标志
        self._cancel_flags[task_id] = True

        # 如果任务正在运行，等待其结束
        if task_id in self._running_tasks:
            # 更新状态为取消中
            await self.repo.update_status(task_id, TaskStatus.CANCELLED)
            await self.repo.add_event(task_id, TaskEventType.CANCELLED)

        return True

    async def execute_task(self, task_id: int) -> dict[str, Any]:
        """
        同步执行任务

        Args:
            task_id: 任务 ID

        Returns:
            任务结果
        """
        print(f"[TaskManager] 开始执行任务 {task_id}")
        try:
            result = await self._execute_task(task_id)
            print(f"[TaskManager] 任务 {task_id} 执行完成")
            return result
        except Exception as e:
            print(f"[TaskManager] 任务 {task_id} 执行失败: {e}")
            raise

    async def _execute_task(self, task_id: int) -> dict[str, Any]:
        """
        内部任务执行方法

        Args:
            task_id: 任务 ID

        Returns:
            任务结果
        """
        print(f"[TaskManager._execute_task] 开始执行任务 {task_id}")

        task = await self.get_task(task_id)
        if not task:
            print(f"[TaskManager._execute_task] 任务 {task_id} 不存在！")
            raise ValueError(f"Task {task_id} not found")

        print(f"[TaskManager._execute_task] 任务 {task_id} 类型={task.task_type}, 状态={task.status}")

        # 检查取消标志
        if self._cancel_flags.get(task_id, False):
            await self.repo.update_status(task_id, TaskStatus.CANCELLED)
            await self.repo.add_event(task_id, TaskEventType.CANCELLED)
            del self._cancel_flags[task_id]
            return {"cancelled": True}

        # 获取执行器
        # 使用 TaskExecutorRegistry 获取执行器
        executor = TaskExecutorRegistry.create(task.task_type.value)
        if not executor:
            error_msg = f"No executor registered for task type: {task.task_type}"
            await self.repo.update_status(task_id, TaskStatus.FAILED, error_msg)
            await self.repo.add_event(
                task_id, TaskEventType.FAILED, {"error": error_msg}
            )
            raise ValueError(error_msg)

        # 更新状态为运行中
        await self.repo.update_status(task_id, TaskStatus.RUNNING)
        await self.repo.add_event(task_id, TaskEventType.STARTED)

        result: dict[str, Any] = {}

        try:
            # 执行任务
            result = await executor.execute(
                task_id=task_id,
                params=task.params,
                on_progress=self._on_progress(task_id),
                on_event=self._on_event(task_id),
                check_cancelled=lambda: self._cancel_flags.get(task_id, False),
            )

            # 检查是否被取消
            if self._cancel_flags.get(task_id, False):
                await self.repo.update_status(task_id, TaskStatus.CANCELLED)
                await self.repo.add_event(task_id, TaskEventType.CANCELLED)
                del self._cancel_flags[task_id]
                return {"cancelled": True}

            # 标记完成
            await self.repo.update_status(task_id, TaskStatus.COMPLETED)
            await self.repo.update_result(task_id, result)
            await self.repo.add_event(
                task_id, TaskEventType.COMPLETED, {"result": result}
            )

        except Exception as e:
            # 标记失败
            error_msg = str(e)
            await self.repo.update_status(task_id, TaskStatus.FAILED, error_msg)
            await self.repo.add_event(
                task_id, TaskEventType.FAILED, {"error": error_msg}
            )
            raise

        finally:
            # 清理
            if task_id in self._running_tasks:
                del self._running_tasks[task_id]
            if task_id in self._cancel_flags:
                del self._cancel_flags[task_id]

        return result

    def _on_progress(self, task_id: int) -> ProgressCallback:
        """
        创建进度回调

        Args:
            task_id: 任务 ID

        Returns:
            进度回调函数
        """
        async def update(current: int, total: int, message: str | None = None, intermediate_result: dict[str, Any] | None = None):
            # 创建新的 session 避免并发冲突
            from src.core.database import get_async_session

            async with get_async_session() as db:
                repo = TaskRepository(db)
                await repo.update_progress(task_id, current, total, message, intermediate_result)
                event_data: dict[str, Any] = {"current": current, "total": total, "message": message}
                if intermediate_result:
                    event_data["result"] = intermediate_result
                await repo.add_event(
                    task_id,
                    TaskEventType.PROGRESS,
                    event_data,
                )

        def sync_wrapper(current: int, total: int, message: str | None = None, intermediate_result: dict[str, Any] | None = None):
            # 在新的事件循环中运行异步函数
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(update(current, total, message, intermediate_result))
            except RuntimeError:
                # 没有运行中的事件循环，创建新的
                asyncio.run(update(current, total, message, intermediate_result))

        return sync_wrapper

    def _on_event(self, task_id: int) -> EventCallback:
        """
        创建事件回调

        Args:
            task_id: 任务 ID

        Returns:
            事件回调函数
        """
        async def add(event_type: TaskEventType, data: dict[str, Any] | None = None):
            # 创建新的 session 避免并发冲突
            from src.core.database import get_async_session

            async with get_async_session() as db:
                repo = TaskRepository(db)
                await repo.add_event(task_id, event_type, data)

        def sync_wrapper(
            event_type: TaskEventType, data: dict[str, Any] | None = None
        ):
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(add(event_type, data))
            except RuntimeError:
                asyncio.run(add(event_type, data))

        return sync_wrapper
