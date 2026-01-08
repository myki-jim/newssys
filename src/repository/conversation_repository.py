"""
对话 Repository 模块
负责对话和消息的持久化操作
"""

import json
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.repository.base import BaseRepository
from src.core.models import ConversationCreate, ConversationUpdate, MessageCreate
from src.core.orm_models import ConversationOrm, MessageOrm


class ConversationRepository(BaseRepository):
    """对话数据访问层"""

    TABLE_NAME = "conversations"

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create(self, data: ConversationCreate) -> dict[str, Any]:
        """创建新对话"""
        now = datetime.now()
        orm_obj = ConversationOrm(
            title=data.title,
            mode=data.mode,
            web_search_enabled=1 if data.web_search_enabled else 0,
            internal_search_enabled=1 if data.internal_search_enabled else 0,
            created_at=now,
            updated_at=now,
        )
        self.session.add(orm_obj)
        await self.session.commit()
        await self.session.refresh(orm_obj)
        return self._orm_to_dict(orm_obj)

    async def fetch_by_id(self, conversation_id: int) -> dict[str, Any] | None:
        """根据ID获取对话"""
        result = await self.session.execute(
            select(ConversationOrm).where(ConversationOrm.id == conversation_id)
        )
        orm_obj = result.scalar_one_or_none()
        if orm_obj:
            return self._orm_to_dict(orm_obj)
        return None

    async def fetch_many(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """获取对话列表"""
        result = await self.session.execute(
            select(ConversationOrm)
            .order_by(ConversationOrm.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._orm_to_dict(orm) for orm in result.scalars().all()]

    async def update(self, conversation_id: int, data: ConversationUpdate) -> dict[str, Any]:
        """更新对话"""
        result = await self.session.execute(
            select(ConversationOrm).where(ConversationOrm.id == conversation_id)
        )
        orm_obj = result.scalar_one_or_none()
        if not orm_obj:
            raise ValueError(f"Conversation {conversation_id} not found")

        if data.title is not None:
            orm_obj.title = data.title
        if data.mode is not None:
            orm_obj.mode = data.mode
        if data.web_search_enabled is not None:
            orm_obj.web_search_enabled = 1 if data.web_search_enabled else 0
        if data.internal_search_enabled is not None:
            orm_obj.internal_search_enabled = 1 if data.internal_search_enabled else 0
        orm_obj.updated_at = datetime.now()

        await self.session.commit()
        await self.session.refresh(orm_obj)
        return self._orm_to_dict(orm_obj)

    async def delete(self, conversation_id: int) -> bool:
        """删除对话"""
        result = await self.session.execute(
            select(ConversationOrm).where(ConversationOrm.id == conversation_id)
        )
        orm_obj = result.scalar_one_or_none()
        if orm_obj:
            await self.session.delete(orm_obj)
            await self.session.commit()
            return True
        return False

    def _orm_to_dict(self, orm: ConversationOrm) -> dict[str, Any]:
        """ORM对象转字典"""
        return {
            "id": orm.id,
            "title": orm.title,
            "mode": orm.mode,
            "web_search_enabled": bool(orm.web_search_enabled),
            "internal_search_enabled": bool(orm.internal_search_enabled),
            "created_at": orm.created_at,
            "updated_at": orm.updated_at,
        }


class MessageRepository(BaseRepository):
    """消息数据访问层"""

    TABLE_NAME = "messages"

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create(self, data: MessageCreate) -> dict[str, Any]:
        """创建新消息"""
        orm_obj = MessageOrm(
            conversation_id=data.conversation_id,
            role=data.role,
            content=data.content,
            agent_state=json.dumps(data.agent_state) if data.agent_state else None,
            search_results=json.dumps(data.search_results) if data.search_results else None,
            created_at=datetime.now(),
        )
        self.session.add(orm_obj)
        await self.session.commit()
        await self.session.refresh(orm_obj)
        return self._orm_to_dict(orm_obj)

    async def fetch_by_conversation(
        self,
        conversation_id: int,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """获取对话的所有消息"""
        result = await self.session.execute(
            select(MessageOrm)
            .where(MessageOrm.conversation_id == conversation_id)
            .order_by(MessageOrm.created_at.asc())
            .limit(limit)
        )
        return [self._orm_to_dict(orm) for orm in result.scalars().all()]

    def _orm_to_dict(self, orm: MessageOrm) -> dict[str, Any]:
        """ORM对象转字典"""
        return {
            "id": orm.id,
            "conversation_id": orm.conversation_id,
            "role": orm.role,
            "content": orm.content,
            "agent_state": json.loads(orm.agent_state) if orm.agent_state else None,
            "search_results": json.loads(orm.search_results) if orm.search_results else None,
            "created_at": orm.created_at,
        }
