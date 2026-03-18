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
            "last_check_at": scheduler.last_check_at.isoformat() if scheduler.last_check_at else None,
            "last_error": scheduler.last_error,
        },
    )


@router.post("/trigger", response_model=APIResponse[dict])
async def trigger_scheduler():
    """手动触发一次调度检查"""
    executed_count = await get_scheduler().trigger_once()
    return APIResponse(
        success=True,
        data={
            "message": f"成功执行 {executed_count} 个任务" if executed_count else "没有到期任务",
            "count": executed_count,
        },
    )
