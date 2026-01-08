"""
调度器管理 API
提供调度器状态查询和手动触发功能
"""

from typing import Any

from fastapi import APIRouter

from src.api.schemas import APIResponse
from src.services.scheduler_service import get_scheduler

router = APIRouter(prefix="/scheduler", tags=["调度器管理"])


@router.get("/status", response_model=APIResponse[dict[str, Any]])
async def get_scheduler_status():
    """获取调度器状态"""
    scheduler = get_scheduler()
    return APIResponse(
        success=True,
        data={
            "running": scheduler.running,
            "check_interval": scheduler.check_interval,
        },
    )


@router.post("/trigger", response_model=APIResponse[dict])
async def trigger_scheduler():
    """手动触发一次调度检查"""
    from src.core.database import get_async_session
    from src.repository.schedule_repository import ScheduleRepository
    from src.services.schedule_executor import ScheduleExecutor

    async with get_async_session() as db:
        repo = ScheduleRepository(db)
        executor = ScheduleExecutor()

        due_schedules = await repo.get_due_schedules()

        if not due_schedules:
            return APIResponse(
                success=True,
                data={"message": "没有到期任务", "count": 0},
            )

        from src.repository.task_repository import TaskRepository

        task_repo = TaskRepository(db)
        executed_count = 0
        errors = []

        for schedule in due_schedules:
            try:
                task_id = await task_repo.create(
                    {
                        "task_type": f"schedule_{schedule['schedule_type']}",
                        "title": f"手动触发: {schedule['name']}",
                        "params": {"schedule_id": schedule["id"]},
                        "status": "pending",
                    }
                )

                await executor.execute_schedule(schedule["id"], task_id)
                executed_count += 1

            except Exception as e:
                errors.append(f"{schedule['name']}: {str(e)}")

        return APIResponse(
            success=len(errors) == 0,
            data={
                "message": f"成功执行 {executed_count} 个任务",
                "count": executed_count,
                "total": len(due_schedules),
                "errors": errors,
            },
        )
