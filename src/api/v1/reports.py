"""
报告生成 API
/api/v1/reports

支持 SSE 流式生成和状态传输
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import APIResponse
from src.core.models import (
    Report,
    ReportAgentStage,
    ReportCreate,
    ReportStatus,
    ReportTemplate,
    ReportTemplateCreate,
    TaskCreate,
    TaskStatus,
    TaskType,
)
from src.repository.report_repository import ReportRepository, ReportTemplateRepository
from src.repository.task_repository import TaskRepository
from src.services.report_agent import ReportGenerationAgent
from src.services.task_manager import TaskManager


logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# 数据库依赖
# ============================================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    from src.core.database import get_async_session
    async with get_async_session() as session:
        yield session


def build_report_task_title(report_id: int) -> str:
    """生成报告任务标题。"""
    return f"report_generation:{report_id}"


async def get_report_task(db: AsyncSession, report_id: int) -> dict | None:
    """查询与报告关联的任务。"""
    task_repo = TaskRepository(db)
    return await task_repo.find_latest_by_title(build_report_task_title(report_id))


def serialize_report_task_event(event: dict) -> tuple[str, dict] | None:
    """把任务事件转换为前端消费的 SSE 事件。"""
    event_data = event.get("event_data") or {}
    stream_event = event_data.get("stream_event")
    if not stream_event:
        return None

    payload = {k: v for k, v in event_data.items() if k != "stream_event"}
    return stream_event, payload


async def stream_report_events(report_id: int) -> AsyncGenerator[str, None]:
    """通过数据库轮询报告状态和任务事件。"""
    from src.core.database import get_async_session

    async with get_async_session() as stream_db:
        report_repo = ReportRepository(stream_db)
        task_repo = TaskRepository(stream_db)

        report = await report_repo.fetch_by_id(report_id)
        if not report:
            yield f"event: error\ndata: {json.dumps({'error': '报告不存在'}, ensure_ascii=False)}\n\n"
            return

        last_event_id = 0
        yield f"event: start\ndata: {json.dumps({'report_id': report_id}, ensure_ascii=False)}\n\n"

        while True:
            report = await report_repo.fetch_by_id(report_id)
            if not report:
                yield f"event: error\ndata: {json.dumps({'error': '报告不存在'}, ensure_ascii=False)}\n\n"
                return

            task = await get_report_task(stream_db, report_id)

            if task:
                events = await task_repo.get_events(task["id"], limit=500)
                fresh_events = [event for event in events if event["id"] > last_event_id]

                for event in fresh_events:
                    serialized = serialize_report_task_event(event)
                    last_event_id = max(last_event_id, event["id"])
                    if not serialized:
                        continue
                    event_name, payload = serialized
                    yield f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

            if report["status"] == ReportStatus.COMPLETED.value:
                statistics = {
                    "total_articles": report.get("total_articles", 0),
                    "clustered_articles": report.get("clustered_articles", 0),
                    "event_count": report.get("event_count", 0),
                }
                payload = {
                    "report_id": report_id,
                    "content": report.get("content", ""),
                    "sections": report.get("sections", []),
                    "statistics": statistics,
                }
                yield f"event: complete\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                return

            if report["status"] == ReportStatus.FAILED.value:
                payload = {
                    "report_id": report_id,
                    "error": report.get("error_message") or "报告生成失败",
                }
                yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                return

            if task and task["status"] == TaskStatus.FAILED.value and report["status"] != ReportStatus.FAILED.value:
                payload = {
                    "report_id": report_id,
                    "error": task.get("error_message") or "报告任务失败",
                }
                yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                return

            yield ": keep-alive\n\n"
            await asyncio.sleep(1)


# ============================================================================
# 报告列表
# ============================================================================

@router.get("")
async def list_reports(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: ReportStatus | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """获取报告列表"""
    repo = ReportRepository(db)
    reports = await repo.fetch_all(limit=limit, offset=offset, status=status)
    return APIResponse(success=True, data=reports)


# ============================================================================
# 报告生成（SSE 流式）
# ============================================================================

@router.post("/generate")
async def generate_report(
    request: ReportCreate,
):
    """
    生成报告（SSE 流式输出）

    返回 Server-Sent Events:
    - event: start - 开始生成，返回 report_id
    - event: state - Agent 状态更新
    - event: complete - 完成
    - event: error - 错误
    """
    async def event_stream():
        from src.core.database import get_async_session

        async with get_async_session() as db:
            repo = ReportRepository(db)
            template_repo = ReportTemplateRepository(db)

            template = None
            if request.template_id:
                template = await template_repo.fetch_by_id(request.template_id)
            else:
                template = await template_repo.fetch_default()

            if template is None:
                yield f"event: error\ndata: {json.dumps({'error': '未找到可用报告模板'}, ensure_ascii=False)}\n\n"
                return

            report_data = await repo.create(request)
            report_id = report_data["id"]
            logger.info("创建报告任务: %s", report_id)

            manager = TaskManager(db)
            await manager.create_task(
                task_type=TaskType.GENERATE_REPORT,
                title=build_report_task_title(report_id),
                params={
                    "report_id": report_id,
                    "template_id": template["id"],
                },
                auto_start=False,
            )

        async for chunk in stream_report_events(report_id):
            yield chunk

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
# 报告模板（必须在 /{report_id} 之前）
# ============================================================================

@router.get("/templates")
async def list_templates(
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """获取所有模板"""
    repo = ReportTemplateRepository(db)
    templates = await repo.fetch_all(limit=limit)
    return APIResponse(success=True, data=templates)


@router.get("/templates/default")
async def get_default_template(
    db: AsyncSession = Depends(get_db),
):
    """获取默认模板"""
    repo = ReportTemplateRepository(db)
    template = await repo.fetch_default()
    if not template:
        return APIResponse(success=False, message="未找到默认模板")
    return APIResponse(success=True, data=template)


@router.get("/templates/{template_id}")
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取模板详情"""
    repo = ReportTemplateRepository(db)
    template = await repo.fetch_by_id(template_id)
    if not template:
        return APIResponse(success=False, message="模板不存在")
    return APIResponse(success=True, data=template)


@router.post("/templates")
async def create_template(
    data: ReportTemplateCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建模板"""
    repo = ReportTemplateRepository(db)
    template = await repo.create(data)
    return APIResponse(success=True, data=template)


@router.put("/templates/{template_id}")
async def update_template(
    template_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """更新模板"""
    repo = ReportTemplateRepository(db)
    template = await repo.update(template_id, data)
    if not template:
        return APIResponse(success=False, message="模板不存在")
    return APIResponse(success=True, data=template)


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除模板"""
    repo = ReportTemplateRepository(db)
    success = await repo.delete(template_id)
    if not success:
        return APIResponse(success=False, message="模板不存在")
    return APIResponse(success=True, data={"deleted_id": template_id})


# ============================================================================
# 预设时间范围（必须在 /{report_id} 之前）
# ============================================================================

@router.get("/presets/time-ranges")
async def get_time_range_presets():
    """获取时间范围预设"""
    now = datetime.now()

    presets = {
        "本周": {
            "start": (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0),
            "end": now.replace(hour=23, minute=59, second=59),
        },
        "上周": {
            "start": (now - timedelta(days=now.weekday() + 7)).replace(hour=0, minute=0, second=0),
            "end": (now - timedelta(days=now.weekday() + 1)).replace(hour=23, minute=59, second=59),
        },
        "本月": {
            "start": now.replace(day=1, hour=0, minute=0, second=0),
            "end": now,
        },
        "上月": {
            "start": (now.replace(day=1) - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0),
            "end": now.replace(day=1, hour=0, minute=0, second=0) - timedelta(seconds=1),
        },
        "最近7天": {
            "start": now - timedelta(days=7),
            "end": now,
        },
        "最近30天": {
            "start": now - timedelta(days=30),
            "end": now,
        },
    }

    # 转换为 ISO 格式
    formatted_presets = {}
    for name, range_data in presets.items():
        formatted_presets[name] = {
            "start": range_data["start"].isoformat(),
            "end": range_data["end"].isoformat(),
        }

    return APIResponse(success=True, data=formatted_presets)


# ============================================================================
# 报告流式更新（必须在 /{report_id} 之前）
# ============================================================================

@router.get("/{report_id}/stream")
async def stream_report_updates(
    report_id: int,
):
    """
    获取报告的实时流式更新（SSE）
    用于详情页实时显示生成进度和AI内容
    """
    return StreamingResponse(
        stream_report_events(report_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# 报告详情（必须在最后，因为它是路径参数）
# ============================================================================

@router.get("/{report_id}")
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取报告详情"""
    repo = ReportRepository(db)
    report = await repo.fetch_by_id(report_id)
    if not report:
        return APIResponse(success=False, message="报告不存在")
    return APIResponse(success=True, data=report)


@router.delete("/{report_id}")
async def delete_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除报告"""
    repo = ReportRepository(db)
    success = await repo.delete(report_id)
    if not success:
        return APIResponse(success=False, message="报告不存在")
    return APIResponse(success=True, data={"deleted_id": report_id})


@router.post("/{report_id}/complete")
async def complete_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    手动完成报告合并
    用于当报告生成过程中SSE连接断开，板块已生成但未最终合并的情况
    """
    from src.services.report_agent import ReportGenerationAgent

    repo = ReportRepository(db)
    report = await repo.fetch_by_id(report_id)

    if not report:
        return APIResponse(success=False, message="报告不存在")

    if report["status"] == "completed":
        return APIResponse(success=False, message="报告已完成，无需再次合并")

    if not report.get("sections") or len(report["sections"]) == 0:
        return APIResponse(success=False, message="报告没有已生成的板块，无法完成合并")

    try:
        # 获取统计数据
        total_articles = report.get("total_articles", 0)
        clustered_articles = report.get("clustered_articles", 0)
        event_count = report.get("event_count", 0)

        statistics = {
            "total_articles": total_articles,
            "clustered_articles": clustered_articles,
            "event_count": event_count,
        }

        # 创建临时报告对象用于合并
        from src.core.models import Report
        temp_report = Report(
            id=report_id,
            title=report["title"],
            time_range_start=report["time_range_start"],
            time_range_end=report["time_range_end"],
        )

        # 使用 agent 的合并方法
        agent = ReportGenerationAgent(db)

        # 从数据库中提取事件（如果有存储的话，否则使用空列表）
        events = report.get("events", [])

        # 执行合并
        final_content = await agent._merge_report(
            sections=report["sections"],
            report=temp_report,
            events=events,
            statistics=statistics,
        )

        # 更新报告为完成状态
        await repo.update(report_id, {
            "status": ReportStatus.COMPLETED,
            "content": final_content,
            "agent_progress": 100,
            "agent_message": "报告已完成",
            "completed_at": datetime.now().isoformat(),
        })

        logger.info(f"报告 {report_id} 手动合并完成")

        return APIResponse(
            success=True,
            data={
                "message": "报告合并完成",
                "content_length": len(final_content),
                "sections_count": len(report["sections"]),
            },
        )

    except Exception as e:
        logger.error(f"手动完成报告失败: {e}", exc_info=True)
        return APIResponse(success=False, message=f"合并失败: {str(e)}")
