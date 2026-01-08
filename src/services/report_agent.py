"""
报告生成 Agent 服务
负责协调文章聚类、事件提取和报告生成的完整流程
"""

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import (
    Report,
    ReportAgentStage,
    ReportAgentState,
    ReportStatus,
    ReportTemplate,
)
from src.repository.article_repository import ArticleRepository
from src.services.article_clustering import ArticleClusteringService
from src.services.event_extraction import EventSelectionService
from src.services.keyword_generator import KeywordGenerator
from src.services.openai_client import get_openai_client


logger = logging.getLogger(__name__)


class ReportGenerationAgent:
    """
    报告生成 Agent
    协调完整的报告生成流程，支持流式状态传输
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.article_repo = ArticleRepository(db)
        self.clustering_service = ArticleClusteringService(db)
        self.event_service = EventSelectionService()
        self.keyword_generator = KeywordGenerator()
        self.ai_client = get_openai_client()

    async def generate_report(
        self,
        report: Report,
        template: ReportTemplate | None = None,
        on_state_update: Callable[[ReportAgentState], None] | None = None,
        on_section_stream: Callable[[str, str], None] | None = None,
    ) -> AsyncGenerator[ReportAgentState, None]:
        """
        生成报告（流式状态）

        Args:
            report: 报告配置
            template: 报告模板（可选）
            on_state_update: 状态更新回调
            on_section_stream: 板块流式输出回调 (section_title, chunk)

        Yields:
            Agent 状态
        """
        try:
            # 阶段1：初始化
            yield await self._update_state(
                ReportAgentStage.INITIALIZING,
                0,
                "正在初始化报告生成...",
                on_state_update,
            )

            # 阶段2：筛选文章
            yield await self._update_state(
                ReportAgentStage.FILTERING_ARTICLES,
                10,
                f"正在筛选 {report.time_range_start} 到 {report.time_range_end} 的文章...",
                on_state_update,
            )

            articles = await self.article_repo.fetch_by_timerange(
                start_date=report.time_range_start,
                end_date=report.time_range_end,
            )

            total_articles = len(articles)
            yield await self._update_state(
                ReportAgentStage.FILTERING_ARTICLES,
                20,
                f"找到 {total_articles} 篇文章",
                on_state_update,
                {"total_articles": total_articles},
            )

            # 阶段3：AI 生成关键字
            yield await self._update_state(
                ReportAgentStage.GENERATING_KEYWORDS,
                25,
                "正在使用 AI 生成关键字...",
                on_state_update,
            )

            keywords = await self.keyword_generator.generate_keywords(
                title=report.title,
                time_start=report.time_range_start,
                time_end=report.time_range_end,
                user_prompt=report.custom_prompt,
                language=report.language,
                max_keywords=10,
            )

            logger.info(f"AI 生成了 {len(keywords)} 个关键字: {keywords}")

            # 发送关键字到前端
            yield await self._update_state(
                ReportAgentStage.GENERATING_KEYWORDS,
                28,
                f"生成了 {len(keywords)} 个关键字: {', '.join(keywords[:5])}{'...' if len(keywords) > 5 else ''}",
                on_state_update,
                {"keywords": keywords},
            )

            # 阶段4：聚类文章
            yield await self._update_state(
                ReportAgentStage.CLUSTERING_ARTICLES,
                30,
                "正在聚类去重文章...",
                on_state_update,
            )

            clusters = await self.clustering_service.cluster_articles_by_timerange(
                start_date=report.time_range_start,
                end_date=report.time_range_end,
                language=report.language,
                keywords=keywords,  # 传递关键字用于评分筛选
                min_score=20.0,  # 最低分数阈值
            )

            clustered_articles = len(clusters)
            yield await self._update_state(
                ReportAgentStage.CLUSTERING_ARTICLES,
                40,
                f"聚类完成：{total_articles} 篇文章去重后为 {clustered_articles} 篇",
                on_state_update,
                {
                    "total_articles": total_articles,
                    "clustered_articles": clustered_articles,
                },
            )

            # 阶段4：提取重点事件
            yield await self._update_state(
                ReportAgentStage.EXTRACTING_EVENTS,
                50,
                f"正在提取重点事件（最多 {report.max_events} 个）...",
                on_state_update,
            )

            events = await self.event_service.select_top_events(
                clusters=clusters,
                max_events=report.max_events,
            )

            event_count = len(events)
            yield await self._update_state(
                ReportAgentStage.EXTRACTING_EVENTS,
                60,
                f"提取了 {event_count} 个重点事件",
                on_state_update,
                {
                    "event_count": event_count,
                    "events": [
                        {
                            "title": e["event_title"],
                            "summary": e["event_summary"][:100],
                            "importance": e["importance_score"],
                        }
                        for e in events[:5]
                    ],
                },
            )

            # 阶段5：生成板块（流式，每个板块完成后立即发送）
            sections = []
            section_templates = template.section_template if template else [
                {"title": "重点事件", "description": "本期最重要的新闻事件"},
                {"title": "详细分析", "description": "事件的深度分析"},
                {"title": "总结", "description": "本期总结"},
            ]

            for i, section_template in enumerate(section_templates):
                section_title = section_template.get("title", f"板块{i+1}")
                section_progress = int(70 + (10 * (i + 1) / len(section_templates)))

                # 更新状态：开始生成板块
                # 如果不是第一个板块，先显示短暂的"已完成前一个板块"状态
                if i > 0:
                    prev_section = sections[-1]
                    yield await self._update_state(
                        ReportAgentStage.GENERATING_SECTIONS,
                        section_progress - 2,
                        f"已完成板块「{prev_section['title']}」",
                        on_state_update,
                        {
                            "current_section": section_title,
                            "section_index": i,
                            "total_sections": len(section_templates),
                            "completed_sections": [{"title": s["title"], "content_length": len(s["content"])} for s in sections],
                        },
                    )

                yield await self._update_state(
                    ReportAgentStage.GENERATING_SECTIONS,
                    section_progress,
                    f"正在生成「{section_title}」板块 ({i+1}/{len(section_templates)})...",
                    on_state_update,
                    {
                        "current_section": section_title,
                        "section_index": i,
                        "total_sections": len(section_templates),
                        "completed_sections": [{"title": s["title"], "content_length": len(s["content"])} for s in sections],
                    },
                )

                # 生成单个板块（带流式输出）
                # 创建流式回调
                def stream_callback(chunk: str):
                    if on_section_stream:
                        on_section_stream(section_title, chunk)

                section_content = await self._generate_single_section(
                    events=events,  # 所有板块都能看到所有事件
                    template=template,
                    custom_prompt=report.custom_prompt,
                    section_title=section_title,
                    section_description=section_template.get("description", ""),
                    on_stream_chunk=stream_callback,
                )

                sections.append(section_content)

                # 立即发送已完成的板块
                logger.info(f"板块 '{section_title}' 生成完成，内容长度: {len(section_content['content'])} 字符")

                yield await self._update_state(
                    ReportAgentStage.GENERATING_SECTIONS,
                    int(70 + (10 * (i + 2) / len(section_templates))),
                    f"已完成 {len(sections)}/{len(section_templates)} 个板块",
                    on_state_update,
                    {
                        "completed_sections": [{"title": s["title"], "content_length": len(s["content"])} for s in sections],
                        "sections": sections,  # 发送所有已完成的板块
                        "total_sections": len(section_templates),  # 添加总板块数
                    },
                )

            yield await self._update_state(
                ReportAgentStage.GENERATING_SECTIONS,
                85,
                f"所有板块生成完成",
                on_state_update,
                {"sections": sections},
            )

            # 阶段6：合并报告
            yield await self._update_state(
                ReportAgentStage.MERGING_REPORT,
                90,
                "正在合并最终报告...",
                on_state_update,
            )

            # 构建统计数据
            statistics = {
                "total_articles": total_articles,
                "clustered_articles": clustered_articles,
                "event_count": event_count,
            }

            final_content = await self._merge_report(
                sections=sections,
                report=report,
                events=events,
                statistics=statistics,
            )

            # 完成
            yield await self._update_state(
                ReportAgentStage.COMPLETED,
                100,
                "报告生成完成",
                on_state_update,
                {
                    "content": final_content,
                    "sections": sections,
                    "events": events,
                    "statistics": statistics,
                },
            )

        except Exception as e:
            logger.error(f"报告生成失败: {e}", exc_info=True)
            yield await self._update_state(
                ReportAgentStage.EXTRACTING_EVENTS,  # 保持在当前阶段
                0,
                f"报告生成失败: {str(e)}",
                on_state_update,
                {"error": str(e)},
            )
            raise

    async def _update_state(
        self,
        stage: ReportAgentStage,
        progress: int,
        message: str,
        on_state_update: Callable[[ReportAgentState], None] | None = None,
        data: dict[str, Any] | None = None,
    ) -> ReportAgentState:
        """更新并返回状态"""
        state = ReportAgentState(
            stage=stage,
            progress=progress,
            total=100,
            message=message,
            data=data or {},
        )

        if on_state_update:
            on_state_update(state)

        return state

    async def _generate_single_section(
        self,
        events: list[dict[str, Any]],
        template: ReportTemplate | None = None,
        custom_prompt: str | None = None,
        section_title: str = "板块",
        section_description: str = "",
        on_stream_chunk: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """
        生成单个报告板块

        Args:
            events: 所有事件列表（每个板块都能看到所有事件）
            template: 报告模板
            custom_prompt: 自定义要求
            section_title: 板块标题
            section_description: 板块描述
            on_stream_chunk: 流式输出回调

        Returns:
            板块数据
        """
        # 构建系统提示词
        # 如果模板有 system_prompt，直接使用模板的提示词（完全由模板控制AI行为）
        # 否则使用默认提示词
        if template and template.system_prompt:
            system_prompt = template.system_prompt
            # 附加图片使用要求（确保有图片时尽量添加）
            system_prompt += "\n\n## 图片使用要求\n"
            system_prompt += "- 如果事件相关的文章包含图片，请在报告中引用这些图片，使报告图文并茂\n"
            system_prompt += "- 使用 Markdown 图片语法：![图片描述](图片URL)\n"
            system_prompt += "- 图片应放在相关段落的开头或适当位置，增强可读性\n"
        else:
            system_prompt = (
                "你是一个专业的新闻分析助手，负责根据给定的新闻事件生成结构化的新闻报告。\n\n"
                "请遵循以下规则：\n"
                "1. 基于事件给出准确、全面的分析\n"
                "2. 使用专业、客观、通顺的语言\n"
                "3. 报告应结构化、易读\n"
                "4. 使用Markdown格式\n"
                "5. 标题必须是通顺的完整句子，不要用关键词堆砌\n"
                "6. 每个事件分析必须列出参考文献（文章标题、链接、发布时间）\n"
                "7. 如果文章中有图片，请在报告中引用这些图片，使报告图文并茂\n"
                "8. 使用 Markdown 图片语法引用：![图片描述](图片URL)\n"
                "9. 相关图片应放在事件分析的开头或适当位置，增强可读性\n"
                "10. 优先使用图片来增强报告的可读性和专业性"
            )

        if custom_prompt:
            system_prompt += f"\n\n用户特殊要求：{custom_prompt}"

        logger.info(f"开始生成板块: {section_title}")

        # 构建事件上下文（所有事件），包含文章列表和图片
        events_context = await self._build_events_context_with_articles_and_images(events)

        # 构建用户消息（简洁，只提供必要信息，详细格式由模板的 system_prompt 控制）
        user_message = f"""请根据以下事件，生成报告的"{section_title}"板块。

板块描述：{section_description}

事件列表（共 {len(events)} 个事件）：
{events_context}

请开始生成：
"""

        # 调用 AI 生成板块内容
        content = ""
        try:
            logger.info(f"正在调用 AI 生成板块: {section_title}")
            chunk_count = 0
            async for chunk in self.ai_client.chat(
                user_message=user_message,
                system_prompt=system_prompt,
            ):
                content += chunk
                chunk_count += 1

                # 流式回调：发送AI生成的内容
                if on_stream_chunk:
                    on_stream_chunk(chunk)

                if chunk_count % 10 == 0:
                    logger.info(f"板块 '{section_title}' 已接收 {chunk_count} 个数据块")

            logger.info(f"板块 '{section_title}' 生成完成，内容长度: {len(content)} 字符")

        except Exception as e:
            logger.error(f"AI生成板块 '{section_title}' 失败: {e}", exc_info=True)
            content = f"板块生成失败: {str(e)}"

        return {
            "title": section_title,
            "content": content,
            "description": section_description,
            "event_count": len(events),
        }

    async def _build_events_context_with_articles(self, events: list[dict[str, Any]]) -> str:
        """构建事件上下文（包含文章列表）"""
        if not events:
            return "无相关事件"

        context_parts = []

        # 使用新的数据库会话避免事务冲突
        from src.core.database import get_async_session

        async with get_async_session() as new_db:
            new_article_repo = ArticleRepository(new_db)

            for i, event in enumerate(events, 1):
                # 获取事件的文章
                article_ids = event.get("article_ids", [])
                representative_article_id = event.get("representative_article_id")

                # 构建文章列表
                articles_list = ""
                if article_ids:
                    articles_list = "\n   相关文章："
                    # 从数据库获取文章详情（使用新会话）
                    for article_id in article_ids[:10]:  # 最多显示10篇
                        article = await new_article_repo.get_by_id(article_id)
                        if article:
                            pub_time_str = article.get('publish_time', '')
                            if pub_time_str:
                                try:
                                    # 尝试解析时间
                                    if isinstance(pub_time_str, str):
                                        pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00')).strftime("%Y-%m-%d %H:%M")
                                    else:
                                        pub_time = str(pub_time_str)
                                except:
                                    pub_time = "未知时间"
                            else:
                                pub_time = "未知时间"

                            articles_list += f"\n   - {article.get('title', '无标题')}"
                            articles_list += f"\n     发布时间：{pub_time}"
                            if article.get('url'):
                                articles_list += f"\n     链接：{article['url']}"
                            articles_list += "\n"

                context_parts.append(f"""
{i}. {event['event_title']}
   摘要：{event['event_summary']}
   重要性：{event['importance_score']:.2f}
   关键词：{', '.join(event['keywords'][:5])}{articles_list}
""")

        return "\n".join(context_parts)

    async def _build_events_context_with_articles_and_images(self, events: list[dict[str, Any]]) -> str:
        """构建事件上下文（包含文章列表和图片信息）"""
        if not events:
            return "无相关事件"

        context_parts = []

        # 使用新的数据库会话避免事务冲突
        from src.core.database import get_async_session

        async with get_async_session() as new_db:
            new_article_repo = ArticleRepository(new_db)

            for i, event in enumerate(events, 1):
                # 获取事件的文章
                article_ids = event.get("article_ids", [])
                representative_article_id = event.get("representative_article_id")

                # 构建文章列表和图片信息
                articles_list = ""
                images_section = ""

                if article_ids:
                    articles_list = "\n   相关文章："
                    all_images = []

                    # 从数据库获取文章详情（使用新会话）
                    for article_id in article_ids[:10]:  # 最多显示10篇
                        article = await new_article_repo.get_by_id(article_id)
                        if article:
                            pub_time_str = article.get('publish_time', '')
                            if pub_time_str:
                                try:
                                    # 尝试解析时间
                                    if isinstance(pub_time_str, str):
                                        pub_time = datetime.fromisoformat(pub_time_str.replace('Z', '+00:00')).strftime("%Y-%m-%d %H:%M")
                                    else:
                                        pub_time = str(pub_time_str)
                                except:
                                    pub_time = "未知时间"
                            else:
                                pub_time = "未知时间"

                            articles_list += f"\n   - {article.get('title', '无标题')}"
                            articles_list += f"\n     发布时间：{pub_time}"
                            if article.get('url'):
                                articles_list += f"\n     链接：{article['url']}"

                            # 提取图片信息
                            extra_data = article.get('extra_data', {})
                            if isinstance(extra_data, dict):
                                images = extra_data.get('images', [])
                                if images and isinstance(images, list):
                                    for img_url in images[:3]:  # 每篇文章最多取3张图片
                                        if img_url and img_url not in all_images:
                                            all_images.append(img_url)

                            articles_list += "\n"

                    # 添加图片信息
                    if all_images:
                        images_section = "\n   相关图片："
                        for img_url in all_images[:5]:  # 最多显示5张图片
                            images_section += f"\n   ![相关图片]({img_url})"

                context_parts.append(f"""
{i}. {event['event_title']}
   摘要：{event['event_summary']}
   重要性：{event['importance_score']:.2f}
   关键词：{', '.join(event['keywords'][:5])}{articles_list}{images_section}
""")

        return "\n".join(context_parts)

    async def _generate_sections(
        self,
        events: list[dict[str, Any]],
        template: ReportTemplate | None = None,
        custom_prompt: str | None = None,
        on_section_progress: Callable[[str, int, int], None] | None = None,
    ) -> list[dict[str, Any]]:
        """
        生成报告板块（已废弃，使用 _generate_single_section）

        Args:
            events: 事件列表
            template: 报告模板
            custom_prompt: 自定义要求
            on_section_progress: 进度回调 (title, index, total)

        Returns:
            板块列表
        """
        # 确定板块模板
        if template and template.section_template:
            section_templates = template.section_template
        else:
            # 默认板块
            section_templates = [
                {"title": "重点事件", "description": "本期最重要的新闻事件"},
                {"title": "详细分析", "description": "事件的深度分析"},
                {"title": "总结", "description": "本期总结"},
            ]

        sections = []
        for i, section_template in enumerate(section_templates):
            title = section_template.get("title", f"板块{i+1}")
            description = section_template.get("description", "")

            # 调用进度回调
            if on_section_progress:
                on_section_progress(title, i, len(section_templates))

            logger.info(f"开始生成板块 [{i+1}/{len(section_templates)}]: {title}")

            # 生成单个板块
            section = await self._generate_single_section(
                events=events,  # 所有板块都能看到所有事件
                template=template,
                custom_prompt=custom_prompt,
                section_title=title,
                section_description=description,
            )

            sections.append(section)

        logger.info(f"所有板块生成完成，共 {len(sections)} 个板块")
        return sections

    def _build_events_context(self, events: list[dict[str, Any]]) -> str:
        """构建事件上下文"""
        if not events:
            return "无相关事件"

        context_parts = []
        for i, event in enumerate(events, 1):
            context_parts.append(f"""
{i}. {event['event_title']}
   摘要：{event['event_summary']}
   相关文章数：{event['article_count']}
   重要性：{event['importance_score']:.2f}
   关键词：{', '.join(event['keywords'][:5])}
""")

        return "\n".join(context_parts)

    async def _merge_report(
        self,
        sections: list[dict[str, Any]],
        report: Report,
        events: list[dict[str, Any]],
        statistics: dict[str, int],
    ) -> str:
        """
        合并最终报告

        Args:
            sections: 板块列表
            report: 报告配置
            events: 事件列表
            statistics: 统计数据

        Returns:
            完整报告内容（Markdown）
        """
        # 构建报告头部
        header = f"""# {report.title}

**时间范围**：{report.time_range_start.strftime('%Y-%m-%d')} 至 {report.time_range_end.strftime('%Y-%m-%d')}

**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 概览

- **文章总数**：{statistics.get('total_articles', 0)}
- **去重后文章**：{statistics.get('clustered_articles', 0)}
- **重点事件数**：{statistics.get('event_count', 0)}

---

"""

        # 合并板块
        sections_content = ""
        for section in sections:
            sections_content += f"\n## {section['title']}\n\n"
            sections_content += section['content']
            sections_content += "\n\n---\n\n"

        # 添加事件列表
        events_content = "\n## 重点事件列表\n\n"
        for i, event in enumerate(events, 1):
            events_content += f"{i}. **{event['event_title']}**\n"
            events_content += f"   - {event['event_summary']}\n"
            events_content += f"   - 关键词：{', '.join(event['keywords'][:5])}\n"
            events_content += f"   - 相关文章：{event['article_count']}篇\n\n"

        return header + sections_content + events_content
