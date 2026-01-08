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
from src.core.models import AgentState, ChatRequest, Conversation, ConversationCreate, ConversationUpdate
from src.repository.conversation_repository import ConversationRepository, MessageRepository
from src.services.ai_agent import AIAgentService


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

    async def event_stream():
        agent_service = AIAgentService(db)

        # 用于收集状态更新的队列
        state_queue = asyncio.Queue()

        def on_state_update(state: AgentState):
            """Agent状态更新回调 - 将状态放入队列"""
            state_dict = {
                "type": "state",
                "data": {
                    "stage": state.stage,
                    "keywords": state.keywords or [],
                    "internal_results": state.internal_results or [],
                    "web_results": state.web_results or [],
                    "progress": state.progress,
                    "total": state.total,
                    "message": state.message,
                }
            }
            try:
                state_queue.put_nowait(json.dumps(state_dict, ensure_ascii=False))
            except:
                pass

        try:
            # 发送开始事件
            yield f"event: start\ndata: {json.dumps({'conversation_id': request.conversation_id})}\n\n"

            # 使用异步任务运行chat
            chat_queue = asyncio.Queue()

            async def run_chat():
                """在后台运行chat，将结果放入队列"""
                full_response = ""
                async for chunk in agent_service.chat(
                    conversation_id=request.conversation_id,
                    message=request.message,
                    mode=request.mode,
                    web_search_enabled=request.web_search_enabled,
                    internal_search_enabled=request.internal_search_enabled,
                    on_state_update=on_state_update,
                ):
                    full_response += chunk
                    await chat_queue.put(("chunk", chunk))
                await chat_queue.put(("done", full_response))

            # 启动聊天任务
            chat_task = asyncio.create_task(run_chat())

            # 主循环：同时处理状态更新和聊天响应
            while True:
                # 检查是否有状态更新
                try:
                    state_data = state_queue.get_nowait()
                    yield f"data: {state_data}\n\n"
                except asyncio.QueueEmpty:
                    pass

                # 检查是否有聊天响应
                try:
                    msg_type, data = chat_queue.get_nowait()
                    if msg_type == "chunk":
                        yield f"event: chunk\ndata: {json.dumps({'text': data}, ensure_ascii=False)}\n\n"
                    elif msg_type == "done":
                        # 发送完成事件
                        yield f"event: end\ndata: {json.dumps({'full_response': data})}\n\n"
                        break
                except asyncio.QueueEmpty:
                    pass

                # 如果聊天任务完成且队列为空，退出循环
                if chat_task.done() and chat_queue.empty():
                    break

                # 短暂休眠避免CPU占用过高
                await asyncio.sleep(0.01)

            # 等待聊天任务完成
            await chat_task

        except Exception as e:
            logger.error(f"Chat error: {e}", exc_info=True)
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
