"""
任务管理 API
/api/v1/tasks
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    APIResponse,
    BadRequestException,
    NotFoundException,
    PaginatedResponse,
    PaginationParams,
)
from src.core.models import (
    Task,
    TaskCreate,
    TaskEventType,
    TaskStatus,
    TaskType,
)
from src.repository.task_repository import TaskRepository
from src.services.task_manager import TaskManager, TaskExecutorRegistry


logger = logging.getLogger(__name__)

router = APIRouter()


def serialize_datetime(obj: Any) -> Any:
    """转换 datetime 对象为 ISO 格式字符串"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def json_dumps_datetime(obj: Any) -> str:
    """支持 datetime 的 JSON 序列化"""
    return json.dumps(obj, default=serialize_datetime)


# ============================================================================
# 依赖注入
# ============================================================================

async def get_db() -> AsyncSession:  # type: ignore
    """获取数据库会话"""
    from src.core.database import get_async_session
    async with get_async_session() as session:
        yield session


# ============================================================================
# 任务列表和统计（具体路由）
# ============================================================================

@router.get("", response_model=APIResponse[PaginatedResponse[dict[str, Any]]])
async def list_tasks(
    pagination: PaginationParams = Depends(),
    status_filter: TaskStatus | None = Query(default=None, description="状态筛选"),
    task_type: str | None = Query(default=None, description="任务类型筛选"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取任务列表

    支持:
    - 分页
    - 按状态筛选
    - 按类型筛选
    """
    repo = TaskRepository(db)

    # 获取总数
    total = await repo.count_by_status(status_filter) if status_filter else 0

    # 获取分页数据
    tasks = await repo.list_tasks(
        status=status_filter,
        task_type=task_type,
        limit=pagination.page_size,
        offset=pagination.offset,
    )

    # 转换为字典
    items = [dict(t) for t in tasks]

    paginated = PaginatedResponse.create(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )

    return APIResponse(success=True, data=paginated)


@router.get("/running", response_model=APIResponse[list[dict[str, Any]]])
async def get_running_tasks(
    task_type: str | None = Query(default=None, description="任务类型筛选"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取正在运行的任务

    返回所有状态为 running 的任务
    """
    repo = TaskRepository(db)
    tasks = await repo.get_running_tasks(task_type)

    return APIResponse(success=True, data=[dict(t) for t in tasks])


@router.get("/stats/summary", response_model=APIResponse[dict[str, Any]])
async def get_task_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    获取任务统计信息

    返回各状态任务的数量
    """
    repo = TaskRepository(db)

    stats = {
        "pending": await repo.count_by_status(TaskStatus.PENDING),
        "running": await repo.count_by_status(TaskStatus.RUNNING),
        "completed": await repo.count_by_status(TaskStatus.COMPLETED),
        "failed": await repo.count_by_status(TaskStatus.FAILED),
        "cancelled": await repo.count_by_status(TaskStatus.CANCELLED),
        "total_types": len(TaskExecutorRegistry.get_registered_types()),
        "registered_types": TaskExecutorRegistry.get_registered_types(),
    }

    return APIResponse(success=True, data=stats)


# ============================================================================
# SSE 流式端点（具体路由，必须在 /{task_id} 之前）
# ============================================================================

@router.get("/crawl-pending/stream")
async def stream_crawl_pending(
    limit_per_source: int = Query(default=10, ge=1, le=100, description="每个源爬取数量"),
    db: AsyncSession = Depends(get_db),
):
    """
    流式执行批量爬取待爬文章 (SSE)

    创建任务并流式返回进度
    """
    # 先用外层 session 创建任务
    manager = TaskManager(db)
    task = await manager.create_task(
        task_type=TaskType.CRAWL_PENDING,
        title=f"批量爬取待爬文章 (每源 {limit_per_source} 条)",
        params={"limit_per_source": limit_per_source},
        auto_start=False,
    )
    task_id = task.id
    print(f"[TASK API] 创建了任务 {task_id}")

    async def event_stream():
        """生成 SSE 事件流"""
        # 创建新的 session 避免并发冲突
        from src.core.database import get_async_session

        async with get_async_session() as stream_db:
            repo = TaskRepository(stream_db)

            # 发送任务创建事件
            yield f"event: created\ndata: {json_dumps_datetime({'task_id': task_id, 'task': dict(task)})}\n\n"

            # 在后台执行任务 - 用新的 session 创建新的 manager
            print(f"[TASK API] 准备启动任务 {task_id}")
            stream_manager = TaskManager(stream_db)
            task_coroutine = stream_manager.execute_task(task_id)
            background_task = asyncio.create_task(task_coroutine)
            print(f"[TASK API] 任务 {task_id} 已提交到后台: {background_task}")

            # 流式返回进度
            check_count = 0
            max_checks = 3600  # 最多检查 1 小时

            while check_count < max_checks:
                # 检查任务状态
                task_dict = await repo.get_by_id(task_id)
                if task_dict is None:
                    break

                yield f"event: status\ndata: {json_dumps_datetime(task_dict)}\n\n"

                # 获取新事件
                events = await repo.get_events(task_id, limit=100)

                for event in events:
                    yield f"event: event\ndata: {json_dumps_datetime(event)}\n\n"

                # 检查任务是否完成
                status = TaskStatus(task_dict["status"])
                if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                    yield f"event: complete\ndata: {json_dumps_datetime(task_dict)}\n\n"
                    break

                check_count += 1
                await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/retry-failed/stream")
async def stream_retry_failed(
    limit: int = Query(default=50, ge=1, le=500, description="重试数量"),
    db: AsyncSession = Depends(get_db),
):
    """
    流式执行批量重试失败文章 (SSE)

    创建任务并流式返回进度
    """
    # 先用外层 session 创建任务
    manager = TaskManager(db)
    task = await manager.create_task(
        task_type=TaskType.RETRY_FAILED,
        title=f"批量重试失败文章 (前 {limit} 条)",
        params={"limit": limit},
        auto_start=False,
    )
    task_id = task.id

    async def event_stream():
        """生成 SSE 事件流"""
        # 创建新的 session 避免并发冲突
        from src.core.database import get_async_session

        async with get_async_session() as stream_db:
            repo = TaskRepository(stream_db)

            # 发送任务创建事件
            yield f"event: created\ndata: {json_dumps_datetime({'task_id': task_id, 'task': dict(task)})}\n\n"

            # 在后台执行任务 - 用新的 session 创建新的 manager
            stream_manager = TaskManager(stream_db)
            asyncio.create_task(stream_manager.execute_task(task_id))

            # 流式返回进度
            check_count = 0
            max_checks = 3600

            while check_count < max_checks:
                task_dict = await repo.get_by_id(task_id)
                if task_dict is None:
                    break

                yield f"event: status\ndata: {json_dumps_datetime(task_dict)}\n\n"

                events = await repo.get_events(task_id, limit=100)
                for event in events:
                    yield f"event: event\ndata: {json_dumps_datetime(event)}\n\n"

                status = TaskStatus(task_dict["status"])
                if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                    yield f"event: complete\ndata: {json_dumps_datetime(task_dict)}\n\n"
                    break

                check_count += 1
                await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# 任务 CRUD（带参数的路由，必须在最后）
# ============================================================================

@router.get("/{task_id}", response_model=APIResponse[dict[str, Any]])
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单个任务详情"""
    manager = TaskManager(db)
    task = await manager.get_task(task_id)

    if task is None:
        raise NotFoundException(f"Task {task_id} not found")

    return APIResponse(success=True, data=dict(task))


@router.post("", response_model=APIResponse[dict[str, Any]], status_code=status.HTTP_201_CREATED)
async def create_task(
    data: TaskCreate,
    auto_start: bool = Query(default=False, description="是否自动开始执行"),
    db: AsyncSession = Depends(get_db),
):
    """
    创建新任务

    支持:
    - 立即执行 (auto_start=true)
    - 延迟执行 (auto_start=false，手动触发)
    """
    manager = TaskManager(db)

    # 检查是否有对应的执行器
    executor = TaskExecutorRegistry.create(data.task_type.value)
    if executor is None:
        raise BadRequestException(
            message=f"No executor registered for task type: {data.task_type.value}",
            details={"task_type": data.task_type.value},
        )

    task = await manager.create_task(
        task_type=data.task_type,
        title=data.title,
        params=data.params,
        auto_start=auto_start,
    )

    logger.info(f"Created task: {task.id} - {task.task_type}")

    return APIResponse(
        success=True,
        data=dict(task),
    )


@router.post("/{task_id}/start", response_model=APIResponse[dict[str, Any]])
async def start_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    手动启动任务

    如果任务状态为 pending，则开始执行
    """
    manager = TaskManager(db)
    task = await manager.get_task(task_id)

    if task is None:
        raise NotFoundException(f"Task {task_id} not found")

    if task.status != TaskStatus.PENDING:
        raise BadRequestException(
            message=f"Task is not in pending status: {task.status.value}",
            details={"task_id": task_id, "current_status": task.status.value},
        )

    # 在后台执行任务
    asyncio.create_task(manager.execute_task(task_id))

    return APIResponse(
        success=True,
        data={"task_id": task_id, "status": "started"},
    )


@router.delete("/{task_id}", response_model=APIResponse[dict[str, Any]])
async def cancel_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    取消任务

    只能取消状态为 pending 或 running 的任务
    """
    manager = TaskManager(db)
    success = await manager.cancel_task(task_id)

    if not success:
        task = await manager.get_task(task_id)
        if task is None:
            raise NotFoundException(f"Task {task_id} not found")
        raise BadRequestException(
            message=f"Cannot cancel task with status: {task.status.value}",
            details={"task_id": task_id, "current_status": task.status.value},
        )

    logger.info(f"Cancelled task: {task_id}")

    return APIResponse(
        success=True,
        data={"task_id": task_id, "status": "cancelled"},
    )


@router.get("/{task_id}/events", response_model=APIResponse[list[dict[str, Any]]])
async def get_task_events(
    task_id: int,
    limit: int = Query(default=100, ge=1, le=1000, description="返回数量限制"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取任务事件列表

    返回任务的执行日志和进度事件
    """
    repo = TaskRepository(db)

    # 检查任务是否存在
    task = await repo.get_by_id(task_id)
    if task is None:
        raise NotFoundException(f"Task {task_id} not found")

    events = await repo.get_events(task_id, limit)

    return APIResponse(success=True, data=events)


@router.get("/{task_id}/stream")
async def stream_task_progress(
    task_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    流式获取任务进度 (SSE)

    使用 Server-Sent Events 实时推送任务进度
    事件类型:
    - status: 状态变更
    - progress: 进度更新
    - event: 任务事件
    - complete: 任务完成
    - error: 任务错误
    """

    async def event_stream():
        """生成 SSE 事件流"""
        # 创建新的 session 避免并发冲突
        from src.core.database import get_async_session

        async with get_async_session() as stream_db:
            repo = TaskRepository(stream_db)

            # 检查任务是否存在
            task = await repo.get_by_id(task_id)
            if task is None:
                yield f"event: error\ndata: {json_dumps_datetime({'error': 'Task not found'})}\n\n"
                return

            # 发送初始状态
            yield f"event: status\ndata: {json_dumps_datetime(dict(task))}\n\n"

            last_event_id = 0
            check_count = 0
            max_checks = 300  # 最多检查 5 分钟 (300 * 1秒)

            while check_count < max_checks:
                # 检查任务状态
                task = await repo.get_by_id(task_id)
                if task is None:
                    break

                # 发送状态更新
                yield f"event: status\ndata: {json_dumps_datetime(dict(task))}\n\n"

                # 获取新事件
                events = await repo.get_events(task_id, limit=100)
                new_events = [e for e in events if e["id"] > last_event_id]

                for event in new_events:
                    yield f"event: event\ndata: {json_dumps_datetime(event)}\n\n"
                    last_event_id = event["id"]

                # 检查任务是否完成
                status = TaskStatus(task["status"])
                if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                    yield f"event: complete\ndata: {json_dumps_datetime(dict(task))}\n\n"
                    break

                check_count += 1
                await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )
