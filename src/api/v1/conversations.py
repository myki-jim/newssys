"""
对话 API
/api/v1/conversations
"""

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import APIResponse
from src.core.database import get_async_session
from src.core.models import ChatRequest, Conversation, ConversationCreate, ConversationUpdate, MessageCreate, TaskStatus, TaskType
from src.repository.conversation_repository import ConversationRepository, MessageRepository
from src.repository.task_repository import TaskRepository
from src.services.task_manager import TaskManager


logger = logging.getLogger(__name__)

router = APIRouter()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with get_async_session() as session:
        yield session


# ============================================================================
# 对话管理
# ============================================================================

@router.get("", response_model=APIResponse[list[dict]])
async def list_conversations(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """获取对话列表"""
    repo = ConversationRepository(db)
    conversations = await repo.fetch_many(limit=limit, offset=offset)
    return APIResponse(success=True, data=conversations)


@router.get("/{conversation_id}", response_model=APIResponse[dict])
async def get_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取对话详情"""
    repo = ConversationRepository(db)
    conversation = await repo.fetch_by_id(conversation_id)
    if not conversation:
        return APIResponse(success=False, message="对话不存在")
    return APIResponse(success=True, data=conversation)


@router.post("", response_model=APIResponse[dict])
async def create_conversation(
    data: ConversationCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建新对话"""
    repo = ConversationRepository(db)
    conversation = await repo.create(data)
    return APIResponse(success=True, data=conversation)


@router.put("/{conversation_id}", response_model=APIResponse[dict])
async def update_conversation(
    conversation_id: int,
    data: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新对话"""
    repo = ConversationRepository(db)
    try:
        conversation = await repo.update(conversation_id, data)
        return APIResponse(success=True, data=conversation)
    except ValueError as e:
        return APIResponse(success=False, message=str(e))


@router.delete("/{conversation_id}", response_model=APIResponse[dict])
async def delete_conversation(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除对话"""
    repo = ConversationRepository(db)
    success = await repo.delete(conversation_id)
    if success:
        return APIResponse(success=True, data={"message": "删除成功"})
    return APIResponse(success=False, message="对话不存在")


# ============================================================================
# 消息管理
# ============================================================================

@router.get("/{conversation_id}/messages", response_model=APIResponse[list[dict]])
async def get_messages(
    conversation_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """获取对话的所有消息"""
    repo = MessageRepository(db)
    messages = await repo.fetch_by_conversation(conversation_id, limit=limit)
    return APIResponse(success=True, data=messages)


# ============================================================================
# AI 对话（SSE流式）
# ============================================================================

@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    流式对话接口（SSE）

    支持两种模式：
    - 直接对话：不使用搜索，直接返回AI响应
    - Agent模式：先搜索再生成响应
    """

    conv_repo = ConversationRepository(db)
    message_repo = MessageRepository(db)
    manager = TaskManager(db)

    if request.conversation_id is None:
        conversation = await conv_repo.create(
            ConversationCreate(
                title=request.message[:50] + "..." if len(request.message) > 50 else request.message,
                mode=request.mode,
                web_search_enabled=request.web_search_enabled,
                internal_search_enabled=request.internal_search_enabled,
            )
        )
        conversation_id = conversation["id"]
    else:
        conversation_id = request.conversation_id
        existing = await conv_repo.fetch_by_id(conversation_id)
        if not existing:
            async def missing_stream():
                yield f"data: {json.dumps({'type': 'error', 'data': {'error': f'Conversation {conversation_id} not found'}}, ensure_ascii=False)}\n\n"

            return StreamingResponse(
                missing_stream(),
                media_type="text/event-stream",
            )

        await conv_repo.update(
            conversation_id,
            ConversationUpdate(
                mode=request.mode,
                web_search_enabled=request.web_search_enabled,
                internal_search_enabled=request.internal_search_enabled,
            ),
        )

    await message_repo.create(
        MessageCreate(
            conversation_id=conversation_id,
            role="user",
            content=request.message,
        )
    )

    task = await manager.create_task(
        task_type=TaskType.AI_CHAT,
        title=f"AI 对话 {conversation_id}",
        params={
            "conversation_id": conversation_id,
            "message": request.message,
            "mode": request.mode,
            "web_search_enabled": request.web_search_enabled,
            "internal_search_enabled": request.internal_search_enabled,
        },
    )

    async def event_stream():
        from src.core.database import get_async_session

        yield f"data: {json.dumps({'type': 'start', 'conversation_id': conversation_id, 'task_id': task.id}, ensure_ascii=False)}\n\n"

        last_event_id = 0
        while True:
            async with get_async_session() as stream_db:
                repo = TaskRepository(stream_db)
                task_data = await repo.get_by_id(task.id)
                if task_data is None:
                    yield f"data: {json.dumps({'type': 'error', 'data': {'error': 'Task not found'}}, ensure_ascii=False)}\n\n"
                    return

                events = await repo.get_events(task.id, limit=500)
                new_events = [event for event in events if event["id"] > last_event_id]

                for event in new_events:
                    last_event_id = event["id"]
                    if event["event_type"] != "info":
                        continue

                    event_data = event.get("event_data") or {}
                    stream_event = event_data.get("stream_event")
                    if stream_event == "state":
                        yield f"data: {json.dumps({'type': 'state', 'data': {'stage': event_data.get('stage'), 'keywords': event_data.get('keywords', []), 'internal_results': event_data.get('internal_results', []), 'web_results': event_data.get('web_results', []), 'progress': event_data.get('progress', 0), 'total': event_data.get('total', 100), 'message': event_data.get('message', '')}}, ensure_ascii=False)}\n\n"
                    elif stream_event == "chunk":
                        yield f"data: {json.dumps({'type': 'chunk', 'data': {'text': event_data.get('text', '')}}, ensure_ascii=False)}\n\n"
                    elif stream_event == "end":
                        yield f"data: {json.dumps({'type': 'end', 'data': {'full_response': event_data.get('full_response', '')}}, ensure_ascii=False)}\n\n"
                        return

                status = TaskStatus(task_data["status"])
                if status == TaskStatus.FAILED:
                    yield f"data: {json.dumps({'type': 'error', 'data': {'error': task_data.get('error_message') or 'AI 对话执行失败'}}, ensure_ascii=False)}\n\n"
                    return
                if status == TaskStatus.CANCELLED:
                    yield f"data: {json.dumps({'type': 'error', 'data': {'error': 'AI 对话已取消'}}, ensure_ascii=False)}\n\n"
                    return
                if status == TaskStatus.COMPLETED:
                    result = task_data.get("result") or {}
                    yield f"data: {json.dumps({'type': 'end', 'data': {'full_response': result.get('full_response', '')}}, ensure_ascii=False)}\n\n"
                    return

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
