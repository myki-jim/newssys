"""
定时任务管理 API
提供定时任务的增删改查、执行等功能
"""

from datetime import datetime, timedelta
from typing import List, Union

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from src.api.schemas import (
    APIResponse,
    ScheduleCreate,
    ScheduleExecuteResponse,
    ScheduleResponse,
    ScheduleUpdate,
)
from src.core.database import get_async_session
from src.repository.schedule_repository import ScheduleRepository
from src.services.schedule_executor import ScheduleExecutor

router = APIRouter(prefix="/schedules", tags=["定时任务"])


def get_schedule_repo() -> ScheduleRepository:
    """获取定时任务仓库依赖"""
    # 这里需要从依赖注入获取，暂时简化
    from src.core.database import get_async_session

    # 注意：实际使用时需要通过依赖注入获取 session
    return ScheduleRepository(None)  # 临时


@router.get("", response_model=APIResponse[List[ScheduleResponse]])
async def list_schedules(
    schedule_type: str | None = Query(None, description="任务类型"),
    status: str | None = Query(None, description="任务状态"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """获取定时任务列表"""
    async with get_async_session() as db:
        repo = ScheduleRepository(db)
        schedules = await repo.list(
            schedule_type=schedule_type, status=status, limit=limit, offset=offset
        )
        return APIResponse(success=True, data=schedules)


@router.get("/{schedule_id}", response_model=APIResponse[ScheduleResponse])
async def get_schedule(schedule_id: int):
    """获取单个定时任务"""
    async with get_async_session() as db:
        repo = ScheduleRepository(db)
        schedule = await repo.get_by_id(schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="定时任务不存在")
        return APIResponse(success=True, data=schedule)


@router.post("", response_model=APIResponse[ScheduleResponse])
async def create_schedule(schedule: ScheduleCreate):
    """创建定时任务"""
    async with get_async_session() as db:
        repo = ScheduleRepository(db)

        # 计算下次运行时间
        next_run_at = datetime.now() + timedelta(minutes=schedule.interval_minutes)

        schedule_data = schedule.model_dump()
        schedule_data["next_run_at"] = next_run_at.isoformat()

        schedule_id = await repo.create(schedule_data)
        created = await repo.get_by_id(schedule_id)

        return APIResponse(success=True, data=created)


@router.put("/{schedule_id}", response_model=APIResponse[ScheduleResponse])
async def update_schedule(schedule_id: int, schedule: ScheduleUpdate):
    """更新定时任务"""
    async with get_async_session() as db:
        repo = ScheduleRepository(db)

        existing = await repo.get_by_id(schedule_id)
        if not existing:
            raise HTTPException(status_code=404, detail="定时任务不存在")

        # 如果更新了间隔，重新计算下次运行时间
        update_data = schedule.model_dump(exclude_unset=True)
        if "interval_minutes" in update_data:
            update_data["next_run_at"] = (
                datetime.now() + timedelta(minutes=update_data["interval_minutes"])
            ).isoformat()

        await repo.update(schedule_id, update_data)
        updated = await repo.get_by_id(schedule_id)

        return APIResponse(success=True, data=updated)


@router.delete("/{schedule_id}", response_model=APIResponse[dict])
async def delete_schedule(schedule_id: int):
    """删除定时任务"""
    async with get_async_session() as db:
        repo = ScheduleRepository(db)

        existing = await repo.get_by_id(schedule_id)
        if not existing:
            raise HTTPException(status_code=404, detail="定时任务不存在")

        await repo.delete(schedule_id)
        return APIResponse(success=True, data={"message": "删除成功"})


@router.post("/{schedule_id}/execute", response_model=APIResponse[dict])
async def execute_schedule(schedule_id: int):
    """立即执行定时任务"""
    async with get_async_session() as db:
        repo = ScheduleRepository(db)

        schedule = await repo.get_by_id(schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="定时任务不存在")

        if schedule["status"] != "active":
            raise HTTPException(status_code=400, detail="任务未激活，无法执行")

        # 创建执行任务
        from src.repository.task_repository import TaskRepository

        task_repo = TaskRepository(db)

        # 根据任务类型选择合适的 task_type
        task_type_mapping = {
            "sitemap_crawl": "sitemap_sync",
            "article_crawl": "crawl_pending",
            "keyword_search": "auto_search",
        }
        mapped_type = task_type_mapping.get(schedule["schedule_type"], "crawl_pending")

        # 直接插入数据库，不使用 TaskCreate
        import json
        from datetime import datetime

        task_data = {
            "task_type": mapped_type,
            "status": "pending",
            "title": f"执行定时任务: {schedule['name']}",
            "params": json.dumps({"schedule_id": schedule_id}),
            "progress_current": 0,
            "progress_total": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        task_id = await task_repo.insert("tasks", task_data, returning="id")

        # 直接执行（不使用后台任务，便于调试）
        try:
            executor = ScheduleExecutor()
            await executor.execute_schedule(schedule_id, task_id)

            # 获取更新后的任务状态
            updated_schedule = await repo.get_by_id(schedule_id)

            return APIResponse(
                success=True,
                data={
                    "task_id": task_id,
                    "schedule_id": schedule_id,
                    "status": "completed",
                    "execution_count": updated_schedule.get("execution_count", 0),
                },
            )
        except Exception as e:
            # 返回错误信息
            import traceback

            error_detail = traceback.format_exc()

            return APIResponse(
                success=False,
                data={
                    "task_id": task_id,
                    "schedule_id": schedule_id,
                    "status": "failed",
                    "error": str(e),
                    "detail": error_detail,
                },
            )


@router.post("/{schedule_id}/pause", response_model=APIResponse[ScheduleResponse])
async def pause_schedule(schedule_id: int):
    """暂停定时任务"""
    async with get_async_session() as db:
        repo = ScheduleRepository(db)

        existing = await repo.get_by_id(schedule_id)
        if not existing:
            raise HTTPException(status_code=404, detail="定时任务不存在")

        await repo.update(schedule_id, {"status": "paused"})
        updated = await repo.get_by_id(schedule_id)

        return APIResponse(success=True, data=updated)


@router.post("/{schedule_id}/resume", response_model=APIResponse[ScheduleResponse])
async def resume_schedule(schedule_id: int):
    """恢复定时任务"""
    async with get_async_session() as db:
        repo = ScheduleRepository(db)

        existing = await repo.get_by_id(schedule_id)
        if not existing:
            raise HTTPException(status_code=404, detail="定时任务不存在")

        # 重新计算下次运行时间
        next_run_at = datetime.now() + timedelta(minutes=existing["interval_minutes"])

        await repo.update(schedule_id, {"status": "active", "next_run_at": next_run_at.isoformat()})
        updated = await repo.get_by_id(schedule_id)

        return APIResponse(success=True, data=updated)
