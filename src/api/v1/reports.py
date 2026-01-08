"""
报告生成 API
/api/v1/reports

支持 SSE 流式生成和状态传输
"""

import asyncio
import json
import logging
from collections import defaultdict
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
)
from src.repository.report_repository import ReportRepository, ReportTemplateRepository
from src.services.report_agent import ReportGenerationAgent


logger = logging.getLogger(__name__)

router = APIRouter()

# 全局状态：存储正在生成的报告的SSE事件队列（支持多个订阅者）
# 结构: {report_id: list[asyncio.Queue]}
# 每个SSE连接都会得到自己的队列，事件会被广播到所有队列
_active_report_streams: dict[int, list[asyncio.Queue]] = {}
_active_report_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


async def _broadcast_event(report_id: int, msg_type: str, data):
    """将事件广播到所有订阅该报告的SSE连接"""
    queues = _active_report_streams.get(report_id, [])
    for queue in queues:
        try:
            await queue.put((msg_type, data))
        except Exception as e:
            logger.error(f"广播事件到队列失败: {e}")

# ============================================================================
# 数据库依赖
# ============================================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    from src.core.database import get_async_session
    async with get_async_session() as session:
        yield session


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
    db: AsyncSession = Depends(get_db),
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
        try:
            # 1. 创建报告记录（占位）
            repo = ReportRepository(db)
            template_repo = ReportTemplateRepository(db)

            # 获取模板
            template = None
            if request.template_id:
                template = await template_repo.fetch_by_id(request.template_id)
            else:
                # 使用默认模板
                template = await template_repo.fetch_default()

            # 创建报告
            report_data = await repo.create(request)
            report_id = report_data["id"]

            logger.info(f"开始生成报告: {report_id}")

            # 创建全局事件队列列表（支持多个SSE订阅者）
            _active_report_streams[report_id] = []

            # 为当前连接创建专用队列
            current_queue = asyncio.Queue()
            _active_report_streams[report_id].append(current_queue)

            # 发送开始事件
            yield f"event: start\ndata: {json.dumps({'report_id': report_id})}\n\n"

            # 状态更新队列（用于生成流程内部通信）
            state_queue = asyncio.Queue()

            # 累积统计数据（避免覆盖）
            accumulated_stats = {
                "total_articles": 0,
                "clustered_articles": 0,
                "event_count": 0,
            }

            # 累积已完成的板块
            accumulated_sections = []

            # 总板块数（从状态中获取）
            total_sections = 0

            # 当前正在流式生成的板块内容
            current_stream_content = {"title": "", "content": ""}

            # 在后台运行生成任务（使用独立的数据库会话）
            async def run_generation():
                nonlocal accumulated_stats, accumulated_sections, total_sections, current_stream_content
                # 创建独立的数据库会话（不使用上下文管理器，避免取消传播）
                from src.core.database import get_async_session_generator

                new_db = get_async_session_generator()
                try:
                    # 创建新的 agent 实例
                    agent = ReportGenerationAgent(new_db)
                    full_result = {}

                    # 安全的队列操作（忽略队列错误，确保任务完整执行）
                    async def safe_put(msg_type: str, data):
                        try:
                            await state_queue.put((msg_type, data))
                        except Exception as e:
                            # 队列可能已关闭，忽略错误继续执行
                            logger.warning(f"队列写入失败（SSE可能已断开），继续后台任务: {e}")

                    # 板块流式输出回调
                    def on_section_stream(section_title: str, chunk: str):
                        nonlocal current_stream_content
                        # 更新当前流式内容
                        if current_stream_content["title"] != section_title:
                            # 新板块开始
                            current_stream_content = {"title": section_title, "content": chunk}
                        else:
                            # 继续当前板块
                            current_stream_content["content"] += chunk

                        # 发送流式内容到队列（非阻塞，忽略错误）
                        try:
                            asyncio.create_task(safe_put("section_stream", {
                                "section_title": section_title,
                                "chunk": chunk,
                                "accumulated_content": current_stream_content["content"],
                            }))
                        except Exception:
                            pass  # 忽略错误，确保生成继续

                    async for state in agent.generate_report(
                        report=Report(**report_data),
                        template=ReportTemplate(**template) if template else None,
                        on_section_stream=on_section_stream,
                    ):
                        full_result = state.data or {}

                        # 提取总板块数
                        if "total_sections" in full_result:
                            total_sections = full_result["total_sections"]

                        # 累积统计数据
                        if "total_articles" in full_result:
                            accumulated_stats["total_articles"] = full_result["total_articles"]
                        if "clustered_articles" in full_result:
                            accumulated_stats["clustered_articles"] = full_result["clustered_articles"]
                        if "event_count" in full_result:
                            accumulated_stats["event_count"] = full_result["event_count"]

                        # 累积已完成的板块
                        if "sections" in full_result:
                            new_sections = full_result["sections"]
                            # 检查是否有新的板块完成
                            if len(new_sections) > len(accumulated_sections):
                                newly_completed = new_sections[len(accumulated_sections):]
                                for section in newly_completed:
                                    accumulated_sections.append(section)

                                # 立即更新数据库：保存已完成的板块和最新的 agent 状态
                                try:
                                    # 构建板块完成消息
                                    completed_count = len(accumulated_sections)
                                    completion_message = f"已完成 {completed_count}/{total_sections} 个板块" if total_sections > 0 else f"已完成 {completed_count} 个板块"

                                    await repo.update(report_id, {
                                        "sections": accumulated_sections,
                                        "agent_message": completion_message,
                                        "agent_progress": int(70 + (10 * completed_count / total_sections)) if total_sections > 0 else 70,
                                        "total_articles": accumulated_stats.get("total_articles", 0),
                                        "clustered_articles": accumulated_stats.get("clustered_articles", 0),
                                        "event_count": accumulated_stats.get("event_count", 0),
                                    })
                                    logger.info(f"已更新数据库，保存 {len(accumulated_sections)} 个板块，状态: {completion_message}")
                                except Exception as db_err:
                                    logger.error(f"更新数据库失败: {db_err}")

                        # 发送状态更新（安全操作）
                        await safe_put("state", state)

                    # 完成（安全操作）
                    await safe_put("done", full_result)
                    logger.info(f"报告 {report_id} 后台任务完成，准备执行最终合并")
                except asyncio.CancelledError:
                    # 任务被取消（不是错误，正常情况）
                    logger.info(f"报告 {report_id} 生成任务被取消")
                    raise
                except Exception as e:
                    logger.error(f"报告生成失败: {e}", exc_info=True)
                    await state_queue.put(("error", str(e)))
                finally:
                    # 确保数据库连接被正确关闭（使用 shield 防止取消）
                    if new_db is not None:
                        try:
                            # 先回滚未提交的事务
                            await asyncio.shield(new_db.rollback())
                        except asyncio.CancelledError:
                            logger.info(f"报告 {report_id} 数据库回滚时被取消")
                        except Exception as e:
                            logger.error(f"数据库回滚失败: {e}")
                        finally:
                            # 无论如何都要关闭连接
                            try:
                                await asyncio.shield(new_db.close())
                            except asyncio.CancelledError:
                                logger.info(f"报告 {report_id} 数据库关闭时被取消")
                            except Exception as e:
                                logger.error(f"关闭数据库连接失败: {e}")

            # 启动生成任务（后台运行，不依赖 SSE 连接）
            task = asyncio.create_task(run_generation())

            # 等待任务完成的回调（清理全局队列）
            async def cleanup_on_task_complete():
                try:
                    await task
                    logger.info(f"报告 {report_id} 生成任务完成")
                except Exception as e:
                    logger.error(f"报告 {report_id} 生成任务失败: {e}")
                finally:
                    # 只在任务完成后清理全局队列，而不是在 SSE 连接断开时
                    if report_id in _active_report_streams:
                        logger.info(f"清理报告 {report_id} 的全局队列")
                        del _active_report_streams[report_id]

            # 启动清理任务
            asyncio.create_task(cleanup_on_task_complete())

            # 主循环：发送状态更新
            try:
                while True:
                    try:
                        msg = await asyncio.wait_for(state_queue.get(), timeout=0.1)

                        if msg[0] == "state":
                            state = msg[1]
                            state_data = state.data if hasattr(state, 'data') else (state.model_dump() if hasattr(state, 'model_dump') else {})

                            # 更新数据库
                            update_data = {
                                "agent_stage": state.stage,
                                "agent_progress": state.progress,
                                "total_articles": accumulated_stats.get("total_articles", 0),
                                "clustered_articles": accumulated_stats.get("clustered_articles", 0),
                                "event_count": accumulated_stats.get("event_count", 0),
                            }

                            # 如果有已完成的板块，使用板块完成消息
                            if len(accumulated_sections) > 0 and total_sections > 0:
                                completed_count = len(accumulated_sections)
                                update_data["agent_message"] = f"已完成 {completed_count}/{total_sections} 个板块"
                                update_data["sections"] = accumulated_sections
                            else:
                                update_data["agent_message"] = state.message

                            await repo.update(report_id, update_data)

                            # 发送状态事件（同时广播到所有订阅者）
                            yield f"event: state\ndata: {json.dumps(state.model_dump(), ensure_ascii=False)}\n\n"
                            await _broadcast_event(report_id, "state", state.model_dump())

                        elif msg[0] == "section_stream":
                            # 发送AI流式输出（同时广播到所有订阅者）
                            stream_data = msg[1]
                            yield f"event: section_stream\ndata: {json.dumps(stream_data, ensure_ascii=False)}\n\n"
                            await _broadcast_event(report_id, "section_stream", stream_data)

                        elif msg[0] == "done":
                            result = msg[1]

                            # 更新报告为完成状态，同时保存统计数据
                            statistics = result.get("statistics", {})
                            await repo.update(report_id, {
                                "status": ReportStatus.COMPLETED,
                                "content": result.get("content", ""),
                                "sections": result.get("sections", []),
                                "total_articles": statistics.get("total_articles", 0),
                                "clustered_articles": statistics.get("clustered_articles", 0),
                                "event_count": statistics.get("event_count", 0),
                            })

                            # 发送完成事件（同时广播到所有订阅者）
                            yield f"event: complete\ndata: {json.dumps(result, ensure_ascii=False)}\n\n"
                            await _broadcast_event(report_id, "complete", result)
                            break

                        elif msg[0] == "error":
                            error_msg = msg[1]

                            # 更新报告为失败状态
                            await repo.update(report_id, {
                                "status": ReportStatus.FAILED,
                                "error_message": error_msg,
                            })

                            # 发送错误事件（同时广播到所有订阅者）
                            yield f"event: error\ndata: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"
                            await _broadcast_event(report_id, "error", {"error": error_msg})
                            break

                    except asyncio.TimeoutError:
                        # 检查任务是否完成
                        if task.done() and state_queue.empty():
                            break
                        continue

                # 等待任务完成（如果 SSE 连接还活着）
                await task

            except GeneratorExit:
                # SSE 连接被客户端关闭，但任务继续在后台运行
                logger.info(f"报告 {report_id} 的 SSE 连接已关闭，生成任务在后台继续运行")
            except Exception as e:
                logger.error(f"报告生成流程失败: {e}", exc_info=True)
                yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"报告生成失败: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

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
    db: AsyncSession = Depends(get_db),
):
    """
    获取报告的实时流式更新（SSE）
    用于详情页实时显示生成进度和AI内容
    """
    async def event_stream():
        try:
            # 检查报告是否存在
            repo = ReportRepository(db)
            report = await repo.fetch_by_id(report_id)
            if not report:
                yield f"event: error\ndata: {json.dumps({'error': '报告不存在'}, ensure_ascii=False)}\n\n"
                return

            # 如果报告已完成或失败，发送当前状态
            if report["status"] in ["completed", "failed"]:
                yield f"event: complete\ndata: {json.dumps({'status': report['status']}, ensure_ascii=False)}\n\n"
                return

            # 检查是否有正在进行的生成任务
            if report_id not in _active_report_streams:
                # 没有正在生成的任务
                yield f"event: complete\ndata: {json.dumps({'status': report['status']}, ensure_ascii=False)}\n\n"
                return

            # 为此连接创建专用队列
            my_queue = asyncio.Queue()
            _active_report_streams[report_id].append(my_queue)
            logger.info(f"报告 {report_id} 的新SSE订阅者，当前订阅者数量: {len(_active_report_streams[report_id])}")

            try:
                # 从专用队列读取事件
                while True:
                    try:
                        # 检查报告状态
                        current_report = await repo.fetch_by_id(report_id)
                        if not current_report:
                            yield f"event: error\ndata: {json.dumps({'error': '报告不存在'}, ensure_ascii=False)}\n\n"
                            break

                        # 如果报告已完成或失败，发送最终状态
                        if current_report["status"] in ["completed", "failed"]:
                            yield f"event: complete\ndata: {json.dumps({'status': current_report['status']}, ensure_ascii=False)}\n\n"
                            break

                        # 从队列获取事件（带超时）
                        try:
                            msg_type, msg_data = await asyncio.wait_for(my_queue.get(), timeout=1.0)

                            if msg_type == "state":
                                yield f"event: state\ndata: {json.dumps(msg_data, ensure_ascii=False)}\n\n"
                            elif msg_type == "section_stream":
                                yield f"event: section_stream\ndata: {json.dumps(msg_data, ensure_ascii=False)}\n\n"
                            elif msg_type == "complete":
                                yield f"event: complete\ndata: {json.dumps(msg_data, ensure_ascii=False)}\n\n"
                                break
                            elif msg_type == "error":
                                yield f"event: error\ndata: {json.dumps(msg_data, ensure_ascii=False)}\n\n"
                                break

                        except asyncio.TimeoutError:
                            # 发送心跳保持连接
                            yield f": keep-alive\n\n"
                            continue

                    except Exception as e:
                        logger.error(f"流式更新错误: {e}", exc_info=True)
                        yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
                        break
            finally:
                # 清理：从订阅列表中移除此队列
                if report_id in _active_report_streams and my_queue in _active_report_streams[report_id]:
                    _active_report_streams[report_id].remove(my_queue)
                    logger.info(f"报告 {report_id} 的SSE订阅者断开，剩余订阅者数量: {len(_active_report_streams[report_id])}")

        except GeneratorExit:
            logger.info(f"报告 {report_id} 的客户端断开连接")
        except Exception as e:
            logger.error(f"流式更新错误: {e}", exc_info=True)

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
