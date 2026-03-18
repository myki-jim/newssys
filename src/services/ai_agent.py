"""
AI Agent 服务
负责对话、关键词生成、搜索等功能
"""

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable
from typing import Any

from duckduckgo_search import DDGS
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import AgentState, MessageCreate
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
        self.ddgs = DDGS()
        self.ai_client = get_openai_client()

    def _resolve_mode(
        self,
        mode: str,
        web_search_enabled: bool,
        internal_search_enabled: bool,
    ) -> tuple[bool, bool]:
        """统一 mode 和布尔开关的语义。"""
        normalized_mode = (mode or "").strip().lower()
        if normalized_mode in {"chat", "direct"}:
            if web_search_enabled or internal_search_enabled:
                return web_search_enabled, internal_search_enabled
            return False, False
        if normalized_mode in {"agent_internal", "internal"}:
            return False, True
        if normalized_mode in {"agent_web", "web"}:
            return True, False
        if normalized_mode in {"agent_both", "agent", "both"}:
            return True, True
        return web_search_enabled, internal_search_enabled

    async def chat(
        self,
        conversation_id: int | None,
        message: str,
        mode: str,
        web_search_enabled: bool,
        internal_search_enabled: bool,
        on_state_update: Callable[[AgentState], None] | None = None,
        on_conversation_ready: Callable[[int], None] | None = None,
        persist_user_message: bool = True,
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
        web_search_enabled, internal_search_enabled = self._resolve_mode(
            mode,
            web_search_enabled,
            internal_search_enabled,
        )

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

        if on_conversation_ready:
            on_conversation_ready(conversation_id)

        # 2. 获取最近对话历史，并按需保存当前用户消息
        if persist_user_message:
            conversation_history = await self.message_repo.fetch_prompt_history(conversation_id, limit=10)
            await self.message_repo.create(
                MessageCreate(
                    conversation_id=conversation_id,
                    role="user",
                    content=message,
                )
            )
        else:
            conversation_history = await self.message_repo.fetch_prompt_history(conversation_id, limit=11)
            if (
                conversation_history
                and conversation_history[-1]["role"] == "user"
                and conversation_history[-1]["content"] == message
            ):
                conversation_history = conversation_history[:-1]

        # 3. 判断是否使用Agent模式
        use_agent = web_search_enabled or internal_search_enabled

        if use_agent:
            # Agent模式
            async for chunk in self._agent_chat(
                conversation_id,
                message,
                conversation_history,
                web_search_enabled,
                internal_search_enabled,
                on_state_update,
            ):
                yield chunk
        else:
            # 直接对话模式
            async for chunk in self._direct_chat(conversation_id, message, conversation_history, on_state_update):
                yield chunk

    async def _direct_chat(
        self,
        conversation_id: int,
        message: str,
        conversation_history: list[dict[str, str]],
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
                conversation_history=conversation_history,
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
        conversation_history: list[dict[str, str]],
        web_search_enabled: bool,
        internal_search_enabled: bool,
        on_state_update: Callable[[AgentState], None] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Agent模式（带搜索）"""
        def emit_state(
            stage: str,
            progress: int,
            message_text: str,
            *,
            keywords: list[str] | None = None,
            internal_results: list[dict[str, Any]] | None = None,
            web_results: list[dict[str, Any]] | None = None,
        ) -> AgentState:
            state = AgentState(
                stage=stage,
                progress=progress,
                total=100,
                message=message_text,
                keywords=keywords or [],
                internal_results=internal_results or [],
                web_results=web_results or [],
            )
            if on_state_update:
                on_state_update(state)
            return state

        emit_state(
            "generating_keywords",
            0,
            "正在分析问题并生成搜索关键词...",
        )

        # 第一步：生成搜索关键词
        keywords = await self._generate_keywords(message)
        emit_state(
            "searching",
            20,
            f"已生成关键词：{', '.join(keywords)}",
            keywords=keywords,
        )

        # 第二步：并行搜索
        search_tasks = []
        if internal_search_enabled:
            search_tasks.append(self._search_internal(conversation_id, keywords, on_state_update, keywords))
        if web_search_enabled:
            search_tasks.append(self._search_web(conversation_id, keywords, on_state_update))

        internal_results: list[dict[str, Any]] = []
        web_results: list[dict[str, Any]] = []
        if search_tasks:
            search_results = await asyncio.gather(*search_tasks)
            result_index = 0
            if internal_search_enabled:
                internal_results = search_results[result_index]
                result_index += 1
            if web_search_enabled:
                web_results = search_results[result_index]

        state = emit_state(
            "searching",
            70,
            "搜索已完成，正在整理上下文...",
            keywords=keywords,
            internal_results=internal_results,
            web_results=web_results,
        )

        # 第三步：生成最终响应
        state = emit_state(
            "generating_response",
            80,
            "正在生成回答...",
            keywords=keywords,
            internal_results=internal_results,
            web_results=web_results,
        )

        # 调试：检查搜索结果
        logger.info(f"Internal results count: {len(internal_results)}")
        logger.info(f"Web results count: {len(web_results)}")

        # 构建搜索结果上下文
        context_str = self.ai_client.build_search_context(
            keywords,
            internal_results,
            web_results,
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
                conversation_history=conversation_history,
            ):
                full_response += chunk
                yield chunk
        except Exception as e:
            logger.error(f"AI agent chat failed: {e}")
            error_response = f"抱歉，AI 服务暂时不可用：{str(e)}"
            yield error_response
            full_response = error_response

        state = emit_state(
            "completed",
            100,
            "完成",
            keywords=keywords,
            internal_results=internal_results,
            web_results=web_results,
        )

        # 保存AI响应
        await self.message_repo.create(
            MessageCreate(
                conversation_id=conversation_id,
                role="assistant",
                content=full_response,
                agent_state=state.model_dump(),
                search_results={"keywords": keywords, "internal_count": len(internal_results), "web_count": len(web_results)},
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
        on_state_update: Callable[[AgentState], None] | None = None,
        state_keywords: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """内部知识库搜索"""
        _ = conversation_id
        if on_state_update:
            on_state_update(
                AgentState(
                    stage="searching_internal",
                    progress=35,
                    total=100,
                    message="正在搜索内部知识库...",
                    keywords=state_keywords or keywords,
                )
            )

        try:
            # 从 articles 表搜索
            results = await self.article_repo.search_articles(
                keywords=keywords,
                limit=10,
                days_ago=90  # 扩大搜索范围到90天
            )

            # 如果没有结果，获取最近的文章作为备选
            if not results:
                if on_state_update:
                    on_state_update(
                        AgentState(
                            stage="searching_internal",
                            progress=42,
                            total=100,
                            message="未找到相关文章，获取最近文章作为上下文...",
                            keywords=state_keywords or keywords,
                        )
                    )

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

            if on_state_update:
                on_state_update(
                    AgentState(
                        stage="searching_internal",
                        progress=50,
                        total=100,
                        message=f"内部搜索完成，找到 {len(formatted_results)} 篇相关文章",
                        keywords=state_keywords or keywords,
                        internal_results=formatted_results,
                    )
                )
            return formatted_results
        except Exception as e:
            logger.error(f"内部搜索失败: {e}")
            if on_state_update:
                on_state_update(
                    AgentState(
                        stage="searching_internal",
                        progress=50,
                        total=100,
                        message=f"内部搜索失败: {str(e)}",
                        keywords=state_keywords or keywords,
                        internal_results=[],
                    )
                )
            return []

    async def _search_web(
        self,
        conversation_id: int,
        keywords: list[str],
        on_state_update: Callable[[AgentState], None] | None = None,
    ) -> list[dict[str, Any]]:
        """联网搜索（DDG）"""
        _ = conversation_id
        if on_state_update:
            on_state_update(
                AgentState(
                    stage="searching_web",
                    progress=35,
                    total=100,
                    message="正在联网搜索...",
                    keywords=keywords,
                )
            )

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
                if on_state_update:
                    on_state_update(
                        AgentState(
                            stage="searching_web",
                            progress=50,
                            total=100,
                            message="联网搜索未找到结果",
                            keywords=keywords,
                            web_results=[],
                        )
                    )
                return []

            logger.info(f"DDG found {len(ddg_results)} results")

            # 爬取搜索结果 - 使用 async context manager 确保 HTTP 客户端正确关闭
            if on_state_update:
                on_state_update(
                    AgentState(
                        stage="searching_web",
                        progress=45,
                        total=100,
                        message=f"正在爬取 {len(ddg_results)} 个搜索结果...",
                        keywords=keywords,
                    )
                )

            async with UniversalScraper() as scraper:
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
                        scraped = await scraper.scrape(url, GENERIC_PARSER_CONFIG)

                        if scraped and scraped.title:
                            article_data = {
                                "title": scraped.title,
                                "url": url,
                                "snippet": result.get("body", ""),
                                "content": scraped.content or "",
                                "publish_time": scraped.publish_time.isoformat() if scraped.publish_time else None,
                            }

                            results.append(article_data)
                            if on_state_update:
                                on_state_update(
                                    AgentState(
                                        stage="searching_web",
                                        progress=45 + int(((i + 1) / max(len(ddg_results), 1)) * 20),
                                        total=100,
                                        message=f"联网搜索进度: {i+1}/{len(ddg_results)}",
                                        keywords=keywords,
                                        web_results=results[-5:],
                                    )
                                )

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

            if on_state_update:
                on_state_update(
                    AgentState(
                        stage="searching_web",
                        progress=65,
                        total=100,
                        message=f"联网搜索完成，找到 {len(results)} 篇文章",
                        keywords=keywords,
                        web_results=results,
                    )
                )
            return results

        except Exception as e:
            logger.error(f"联网搜索失败: {e}")
            if on_state_update:
                on_state_update(
                    AgentState(
                        stage="searching_web",
                        progress=65,
                        total=100,
                        message=f"联网搜索失败: {str(e)}",
                        keywords=keywords,
                        web_results=[],
                    )
                )
            return []
