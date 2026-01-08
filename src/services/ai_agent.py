"""
AI Agent 服务
负责对话、关键词生成、搜索等功能
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Callable
from typing import Any

from duckduckgo_search import DDGS
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import AgentState, ArticleCreate, MessageCreate
from src.repository.article_repository import ArticleRepository
from src.repository.conversation_repository import ConversationRepository, MessageRepository
from src.services.openai_client import get_openai_client
from src.services.universal_scraper import UniversalScraper


logger = logging.getLogger(__name__)


# 通用爬虫配置
GENERIC_PARSER_CONFIG = {
    "title_selector": "h1, title, .title, .headline",
    "content_selector": "article, .content, .post-content, main, .article-body, #content",
    "publish_time_selector": "time, .date, .publish-date, time[datetime]",
    "author_selector": ".author, .byline, [rel=author]",
    "encoding": "utf-8",
}


class AIAgentService:
    """AI Agent 服务"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.conv_repo = ConversationRepository(db)
        self.message_repo = MessageRepository(db)
        self.article_repo = ArticleRepository(db)
        self.scraper = UniversalScraper()
        self.ddgs = DDGS()
        self.ai_client = get_openai_client()

    async def chat(
        self,
        conversation_id: int | None,
        message: str,
        mode: str,
        web_search_enabled: bool,
        internal_search_enabled: bool,
        on_state_update: Callable[[AgentState], None] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        处理对话请求

        Args:
            conversation_id: 对话ID，None表示新对话
            message: 用户消息
            mode: 对话模式
            web_search_enabled: 是否启用联网搜索
            internal_search_enabled: 是否启用内部搜索
            on_state_update: 状态更新回调

        Yields:
            响应文本片段
        """
        # 1. 创建或获取对话
        if conversation_id is None:
            # 创建新对话
            from src.core.models import ConversationCreate
            conversation = await self.conv_repo.create(
                ConversationCreate(
                    title=message[:50] + "..." if len(message) > 50 else message,
                    mode="agent_both" if (web_search_enabled or internal_search_enabled) else "chat",
                    web_search_enabled=web_search_enabled,
                    internal_search_enabled=internal_search_enabled,
                )
            )
            conversation_id = conversation["id"]
        else:
            conversation = await self.conv_repo.fetch_by_id(conversation_id)
            if not conversation:
                raise ValueError(f"Conversation {conversation_id} not found")

        # 2. 保存用户消息
        await self.message_repo.create(
            MessageCreate(
                conversation_id=conversation_id,
                role="user",
                content=message,
            )
        )

        # 3. 判断是否使用Agent模式
        use_agent = web_search_enabled or internal_search_enabled

        if use_agent:
            # Agent模式
            async for chunk in self._agent_chat(
                conversation_id,
                message,
                web_search_enabled,
                internal_search_enabled,
                on_state_update,
            ):
                yield chunk
        else:
            # 直接对话模式
            async for chunk in self._direct_chat(conversation_id, message, on_state_update):
                yield chunk

    async def _direct_chat(
        self,
        conversation_id: int,
        message: str,
        on_state_update: Callable[[AgentState], None] | None = None,
    ) -> AsyncGenerator[str, None]:
        """直接对话模式（无搜索）"""
        system_prompt = """你是一个智能助手，负责回答用户的问题。
请用自然、友好的语气回答，回答要准确、有帮助。"""

        full_response = ""

        # 调用 AI 生成响应
        try:
            async for chunk in self.ai_client.chat(
                user_message=message,
                system_prompt=system_prompt,
            ):
                full_response += chunk
                yield chunk
        except Exception as e:
            logger.error(f"AI chat failed: {e}")
            error_response = f"抱歉，AI 服务暂时不可用：{str(e)}"
            yield error_response
            full_response = error_response

        # 保存AI响应
        await self.message_repo.create(
            MessageCreate(
                conversation_id=conversation_id,
                role="assistant",
                content=full_response,
                agent_state={"stage": "direct_chat"},
            )
        )

    async def _agent_chat(
        self,
        conversation_id: int,
        message: str,
        web_search_enabled: bool,
        internal_search_enabled: bool,
        on_state_update: Callable[[AgentState], None] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Agent模式（带搜索）"""
        state = AgentState(
            stage="generating_keywords",
            progress=0,
            total=100,
            message="正在分析问题并生成搜索关键词...",
        )
        if on_state_update:
            on_state_update(state)

        # 第一步：生成搜索关键词
        keywords = await self._generate_keywords(message)
        state.keywords = keywords
        state.stage = "searching"
        state.progress = 20
        state.message = f"已生成关键词：{', '.join(keywords)}"
        if on_state_update:
            on_state_update(state)

        # 第二步：并行搜索
        search_tasks = []
        if internal_search_enabled:
            search_tasks.append(self._search_internal(conversation_id, keywords, state, on_state_update))
        if web_search_enabled:
            search_tasks.append(self._search_web(conversation_id, keywords, state, on_state_update))

        if search_tasks:
            await asyncio.gather(*search_tasks)

        # 第三步：生成最终响应
        state.stage = "generating_response"
        state.progress = 80
        state.message = "正在生成回答..."
        if on_state_update:
            on_state_update(state)

        # 调试：检查搜索结果
        logger.info(f"Internal results count: {len(state.internal_results)}")
        logger.info(f"Web results count: {len(state.web_results)}")

        # 构建搜索结果上下文
        context_str = self.ai_client.build_search_context(
            keywords,
            state.internal_results,
            state.web_results,
        )

        logger.info(f"Generated context length: {len(context_str)}")

        # 构建系统提示词
        system_prompt = """你是一个智能新闻助手，根据搜索结果回答用户问题。

请遵循以下规则：
1. 基于搜索结果给出准确、全面的回答
2. 如果搜索结果中没有相关信息，明确说明
3. 引用具体的信息来源（标题、链接）
4. 用自然、友好的语言回答
5. 回答应结构化、易读"""

        # 构建用户消息
        user_message = f"""用户问题：{message}

{context_str}

请根据以上搜索结果回答用户问题。"""

        full_response = ""

        # 调用 AI 生成响应
        try:
            async for chunk in self.ai_client.chat(
                user_message=user_message,
                system_prompt=system_prompt,
            ):
                full_response += chunk
                yield chunk
        except Exception as e:
            logger.error(f"AI agent chat failed: {e}")
            error_response = f"抱歉，AI 服务暂时不可用：{str(e)}"
            yield error_response
            full_response = error_response

        state.stage = "completed"
        state.progress = 100
        state.message = "完成"
        if on_state_update:
            on_state_update(state)

        # 保存AI响应
        await self.message_repo.create(
            MessageCreate(
                conversation_id=conversation_id,
                role="assistant",
                content=full_response,
                agent_state=state.model_dump(),
                search_results={"keywords": keywords, "internal_count": len(state.internal_results), "web_count": len(state.web_results)},
            )
        )

    async def _generate_keywords(self, message: str) -> list[str]:
        """生成搜索关键词"""
        try:
            keywords = await self.ai_client.generate_keywords(message, max_keywords=3)
            logger.info(f"Generated keywords: {keywords}")
            return keywords
        except Exception as e:
            logger.error(f"Failed to generate keywords: {e}")
            # 返回默认关键词
            return [message[:20], message[:10] + "相关", "最新消息"][:3]

    async def _search_internal(
        self,
        conversation_id: int,
        keywords: list[str],
        state: AgentState,
        on_state_update: Callable[[AgentState], None] | None = None,
    ) -> None:
        """内部知识库搜索"""
        state.message = "正在搜索内部知识库..."
        if on_state_update:
            on_state_update(state)

        try:
            # 从 articles 表搜索
            results = await self.article_repo.search_articles(
                keywords=keywords,
                limit=10,
                days_ago=90  # 扩大搜索范围到90天
            )

            # 如果没有结果，获取最近的文章作为备选
            if not results:
                state.message = "未找到相关文章，获取最近文章作为上下文..."
                if on_state_update:
                    on_state_update(state)

                # 获取最近的文章
                recent = await self.article_repo.get_latest_articles(limit=10)
                results = recent

            # 格式化结果
            formatted_results = []
            for row in results:
                formatted_results.append({
                    "title": row.get("title", ""),
                    "url": row.get("url", ""),
                    "publish_time": row.get("publish_time"),  # 已经是ISO格式字符串
                    "content": row.get("content", ""),
                    "snippet": (row.get("content") or "")[:200] + "..." if row.get("content") and len(row.get("content") or "") > 200 else row.get("content") or "",
                })

            state.internal_results = formatted_results
            state.message = f"内部搜索完成，找到 {len(formatted_results)} 篇相关文章"
        except Exception as e:
            logger.error(f"内部搜索失败: {e}")
            state.internal_results = []
            state.message = f"内部搜索失败: {str(e)}"

        if on_state_update:
            on_state_update(state)

    async def _search_web(
        self,
        conversation_id: int,
        keywords: list[str],
        state: AgentState,
        on_state_update: Callable[[AgentState], None] | None = None,
    ) -> None:
        """联网搜索（DDG）"""
        state.message = "正在联网搜索..."
        if on_state_update:
            on_state_update(state)

        results = []

        try:
            # 使用所有关键词进行搜索
            search_query = " ".join(keywords)
            logger.info(f"DDG search query: {search_query}")

            # 使用 DDG 搜索
            try:
                ddg_results = self.ddgs.text(
                    search_query,
                    max_results=10
                )
                # 确保结果是列表
                if ddg_results:
                    ddg_results = list(ddg_results)
                else:
                    ddg_results = []
            except Exception as e:
                logger.error(f"DDG search error: {e}")
                ddg_results = []

            if not ddg_results:
                state.message = "联网搜索未找到结果"
                if on_state_update:
                    on_state_update(state)
                return

            logger.info(f"DDG found {len(ddg_results)} results")

            # 爬取搜索结果 - 使用 async context manager 确保 HTTP 客户端正确关闭
            state.message = f"正在爬取 {len(ddg_results)} 个搜索结果..."
            if on_state_update:
                on_state_update(state)

            async with self.scraper:
                for i, result in enumerate(ddg_results):
                    try:
                        url = result.get("href", "")
                        if not url:
                            continue

                        # 跳过常见403网站的链接
                        skip_domains = ["wikipedia.org", "zhihu.com", "tieba.baidu.com", "zhidao.baidu.com"]
                        url_lower = url.lower()
                        should_skip = False
                        for domain in skip_domains:
                            if domain in url_lower:
                                logger.info(f"跳过 {domain} 链接: {url}")
                                should_skip = True
                                break
                        if should_skip:
                            continue

                        # 使用内置爬虫爬取内容（使用通用配置）
                        scraped = await self.scraper.scrape(url, GENERIC_PARSER_CONFIG)

                        if scraped and scraped.title:
                            article_data = {
                                "title": scraped.title,
                                "url": url,
                                "snippet": result.get("body", ""),
                                "content": scraped.content or "",
                                "publish_time": scraped.publish_time.isoformat() if scraped.publish_time else None,
                            }

                            results.append(article_data)

                            # 同时存储到数据库（使用一个通用源ID，假设1为web搜索源）
                            # 先检查URL是否已存在
                            exists = await self.article_repo.exists_by_url(url)
                            if not exists:
                                await self.article_repo.create_from_scraped(scraped, source_id=1)

                            state.message = f"联网搜索进度: {i+1}/{len(ddg_results)}"
                            if on_state_update:
                                on_state_update(state)

                    except Exception as e:
                        logger.warning(f"爬取URL失败 {result.get('href', '')}: {e}")
                        # 即使爬取失败，也保留搜索结果
                        results.append({
                            "title": result.get("title", ""),
                            "url": result.get("href", ""),
                            "snippet": result.get("body", ""),
                            "content": "",
                            "publish_time": None,
                        })

            state.web_results = results
            state.message = f"联网搜索完成，找到 {len(results)} 篇文章"

        except Exception as e:
            logger.error(f"联网搜索失败: {e}")
            state.web_results = []
            state.message = f"联网搜索失败: {str(e)}"

        if on_state_update:
            on_state_update(state)
