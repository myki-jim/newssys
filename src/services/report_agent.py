"""
报告生成 Agent 服务
负责协调文章聚类、事件提取和报告生成的完整流程
"""

import asyncio
import inspect
import logging
import re
from collections.abc import AsyncGenerator, Awaitable, Callable
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
from src.repository.source_repository import SourceRepository
from src.services.article_clustering import ArticleClusteringService
from src.services.citation import ReferenceManager
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
        self.reference_manager = ReferenceManager()

    async def generate_report(
        self,
        report: Report,
        template: ReportTemplate | None = None,
        on_state_update: Callable[[ReportAgentState], Awaitable[None] | None] | None = None,
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
            self.reference_manager = ReferenceManager()
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
                "正在对高相关候选文章做聚类去重...",
            )

            async def handle_clustering_progress(progress_data: dict[str, Any]) -> None:
                current = max(int(progress_data.get("current", 0)), 0)
                total = max(int(progress_data.get("total", 0)), 1)
                clustering_progress = min(39, 30 + int((current / total) * 9))
                await self._update_state(
                    ReportAgentStage.CLUSTERING_ARTICLES,
                    clustering_progress,
                    progress_data.get("message", "正在聚类去重文章..."),
                    on_state_update,
                    {
                        "total_articles": total_articles,
                        "cluster_progress": {
                            "current": current,
                            "total": total,
                            "comparisons": int(progress_data.get("comparisons", 0)),
                            "cluster_count": int(progress_data.get("cluster_count", 0)),
                        },
                    },
                )

            clusters = await self.clustering_service.cluster_articles_by_timerange(
                start_date=report.time_range_start,
                end_date=report.time_range_end,
                language=report.language,
                keywords=keywords,  # 传递关键字用于评分筛选
                min_score=20.0,  # 最低分数阈值
                on_progress=handle_clustering_progress,
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

            # 阶段4：提取重点事件（使用 AI 生成的关键词进行筛选和排序）
            yield await self._update_state(
                ReportAgentStage.EXTRACTING_EVENTS,
                50,
                f"正在提取重点事件（最多 {report.max_events} 个）...",
                on_state_update,
            )

            events = await self.event_service.select_top_events(
                clusters=clusters,
                max_events=report.max_events,
                ai_keywords=keywords,  # 传递 AI 生成的关键词
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
            section_templates = (
                template.section_template
                if template and template.section_template
                else self._default_section_templates(report.title)
            )

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
                section_content["content"] = await self._revise_section_for_quality(
                    content=section_content["content"],
                    events=events,
                    section_title=section_title,
                    section_description=section_template.get("description", ""),
                    custom_prompt=report.custom_prompt,
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
        on_state_update: Callable[[ReportAgentState], Awaitable[None] | None] | None = None,
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
            maybe_awaitable = on_state_update(state)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable

        return state

    def _default_section_templates(self, report_title: str) -> list[dict[str, str]]:
        return [
            {
                "title": "执行摘要与核心判断",
                "description": (
                    f"围绕“{report_title}”给出完整的研究摘要。需要用连续段落先交代研究对象、"
                    "核心发现、主要矛盾和最重要的判断，并明确哪些结论最值得决策者关注。"
                ),
            },
            {
                "title": "事态演变与关键时间线",
                "description": (
                    "按照时间顺序重建近阶段事态如何升级，梳理触发点、升级节点、关键政策动作和舆论拐点。"
                    "不能只罗列事件，必须解释为什么这些节点改变了局势。"
                ),
            },
            {
                "title": "冲突起因、驱动因素与战略意图",
                "description": (
                    "深入分析冲突或议题背后的结构性成因、短期诱因、相关国家或组织的战略目标、"
                    "以及安全、经济、政治和意识形态层面的驱动因素。"
                ),
            },
            {
                "title": "国际社会态度、政策反应与分歧",
                "description": (
                    "分析主要国家、国际组织、地区力量、市场主体和舆论系统的态度差异，"
                    "说明谁支持、谁反对、谁保持克制，以及这种分歧对局势意味着什么。"
                ),
            },
            {
                "title": "风险评估、情景推演与结论",
                "description": (
                    "在现有证据基础上评估局势未来可能演化出的主要风险、约束条件和几个最值得关注的情景，"
                    "最后形成完整的研究性结论，但不要写成空洞总结。"
                ),
            },
        ]

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
            system_prompt += (
                "\n\n补充写作规则：\n"
                "1. 正文必须以完整段落写作，不要使用项目符号、编号清单或“要点式”表达。\n"
                "2. 每一个核心判断都必须给出明确来源，使用 [1]、[2] 这样的引用标记。\n"
                "3. 每段都要展开论证背景、因果链条、利益相关方立场和影响，而不是只下结论。\n"
                "4. 写作风格要接近国际研究机构、智库和学术综述，避免口号、套话和空泛总结。\n"
                "5. 如果存在多方立场分歧，必须交代主要国家、国际组织或市场参与者的不同态度，并说明依据。\n"
                "6. 除“参考文献”部分外，不要使用列表符号。\n"
                "7. 每个自然段都应足够长，通常不少于5句，不要写成两三句就结束的短段。\n"
                "8. 不要使用“一、二、三”或“首先、其次、最后”来拼接空洞提纲。\n"
            )
        else:
            system_prompt = (
                "你是一位世界级国际问题研究员和政策分析作者，负责基于给定新闻证据撰写研究机构风格的深度报告。\n\n"
                "写作规则如下：\n"
                "1. 只能依据给定材料写作，不得补造事实。\n"
                "2. 必须使用 Markdown，但正文必须采用长段落 prose，不要使用项目符号、编号清单或“点状”表达。\n"
                "3. 每个核心事实与判断都必须带来源标记 [1]、[2]。\n"
                "4. 每一段都要展开背景、因果链条、参与方动机、政策含义和潜在影响。\n"
                "5. 如果材料允许，必须呈现时间线、冲突起因、各方立场、国际反应、风险演变和未来情景。\n"
                "6. 语言必须专业、克制、分析性强，接近国际智库、研究报告和学术综述，而不是新闻快讯。\n"
                "7. 标题和小标题必须是完整而有信息量的表述，不能只是关键词堆砌。\n"
                "8. 如果文章中有图片，可适度引用，但图片不是重点，证据和分析才是重点。\n"
                "9. 不要只做概括，必须用材料支撑判断并交代不同国家、组织和舆论主体的态度差异。\n"
                "10. 除“参考文献”标题外，不要单独输出空洞的结论句。\n"
                "11. 每个自然段都必须充分展开，避免短段落、摘要腔和新闻播报腔。\n"
                "12. 不要写“第一，第二，第三”式提纲文本，要把分析自然组织进连续论述之中。"
            )

        if custom_prompt:
            system_prompt += f"\n\n用户特殊要求：{custom_prompt}"

        logger.info(f"开始生成板块: {section_title}")

        # 构建事件上下文（所有事件），包含文章列表和图片
        events_context = await self._build_events_context_with_articles_and_images(events)

        # 构建用户消息（简洁，只提供必要信息，详细格式由模板的 system_prompt 控制）
        user_message = f"""请根据以下证据材料，撰写报告的“{section_title}”板块。

板块描述：{section_description}

可用事件与证据材料（共 {len(events)} 个事件）：
{events_context}

请严格执行以下要求：
1. 输出必须是连贯长段落，不要使用任何项目符号或编号列表。
2. 每段都要充分展开，不能只给一句判断；每段通常至少应达到五句以上的完整展开。
3. 每个核心事实与分析判断都要在句末或段末附上引用标记，如 [1][2]。
4. 要优先呈现因果关系、各方动机、政策影响、国际反应和争议点。
5. 如果证据不足，不要硬写结论，要明确说明不确定性并继续基于现有材料分析。
6. 如果同一问题存在多篇材料，请综合比较它们的差异，而不是重复改写同一篇内容。
7. 不要输出“首先、其次、最后”式浅层套路，要像成熟研究报告一样自然展开。

现在开始撰写这一板块。
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

    async def _revise_section_for_quality(
        self,
        *,
        content: str,
        events: list[dict[str, Any]],
        section_title: str,
        section_description: str,
        custom_prompt: str | None,
    ) -> str:
        if not self._section_needs_rewrite(content):
            return content

        logger.info(f"板块 '{section_title}' 触发质量重写")
        evidence_context = await self._build_events_context_with_articles_and_images(events)
        rewrite_prompt = (
            f"请重写报告板块“{section_title}”。\n\n"
            f"板块目标：{section_description}\n\n"
            "当前版本存在明显问题：它可能过短、像提纲、缺少引用，或没有充分展开。\n"
            "你必须将其改写成研究机构风格的完整章节，满足以下条件：\n"
            "1. 必须全部使用完整段落，不要使用项目符号、编号列表或提纲式句子。\n"
            "2. 每个核心判断必须给出 [1]、[2] 这样的引用。\n"
            "3. 需要显著展开背景、因果、各方立场、影响和不确定性。\n"
            "4. 如果原文已经有可用分析，可保留其有价值部分，但必须重构成更完整的 prose。\n"
            "5. 不要写参考文献列表，只重写正文板块。\n"
        )
        if custom_prompt:
            rewrite_prompt += f"6. 额外用户要求：{custom_prompt}\n"

        rewrite_prompt += (
            "\n现有草稿如下：\n"
            f"{content}\n\n"
            "可用证据如下：\n"
            f"{evidence_context}\n\n"
            "请直接输出重写后的完整板块正文。"
        )

        revised = ""
        try:
            async for chunk in self.ai_client.chat(
                user_message=rewrite_prompt,
                system_prompt=(
                    "你是一位国际问题研究报告作者。你的任务是把低质量草稿改写成"
                    "带引用、展开充分、具有研究机构风格的完整章节。"
                ),
            ):
                revised += chunk
        except Exception as exc:
            logger.error(f"板块 '{section_title}' 重写失败: {exc}", exc_info=True)
            return content

        return revised or content

    def _section_needs_rewrite(self, content: str) -> bool:
        normalized = (content or "").strip()
        if not normalized:
            return True
        if len(normalized) < 900:
            return True
        if len(re.findall(r"\[\d+\]", normalized)) < 2:
            return True
        bullet_like_patterns = (
            r"(?m)^\s*[-*•]\s+",
            r"(?m)^\s*\d+[.)]\s+",
            r"(?m)^\s*[一二三四五六七八九十]+[、.]\s+",
        )
        if any(re.search(pattern, normalized) for pattern in bullet_like_patterns):
            return True
        short_paragraphs = [p.strip() for p in re.split(r"\n\s*\n", normalized) if p.strip()]
        if short_paragraphs and sum(1 for p in short_paragraphs if len(p) < 120) >= max(2, len(short_paragraphs) // 2):
            return True
        if re.search(r"(?m)^\s*[一二三四五六七八九十]+[、.]", normalized):
            return True
        if re.search(r"首先|其次|再次|最后", normalized):
            return True
        return False

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
        source_names = await self._get_source_names()

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
                    articles_list = "\n   证据材料："
                    all_images = []

                    # 从数据库获取文章详情（使用新会话）
                    for article_id in article_ids[:12]:  # 最多显示12篇
                        article = await new_article_repo.get_by_id(article_id)
                        if article:
                            citation_index = self.reference_manager.add_reference(
                                article,
                                source_name=source_names.get(article.get("source_id")),
                            )
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

                            content = article.get("content") or ""
                            normalized_excerpt = " ".join(str(content).split())
                            if len(normalized_excerpt) > 280:
                                normalized_excerpt = normalized_excerpt[:280].rstrip() + "..."

                            source_name = source_names.get(article.get("source_id")) or f"Source {article.get('source_id')}"
                            articles_list += f"\n   [{citation_index}] {article.get('title', '无标题')}"
                            articles_list += f"\n   来源：{source_name}"
                            articles_list += f"\n   发布时间：{pub_time}"
                            if article.get('url'):
                                articles_list += f"\n   链接：{article['url']}"
                            if normalized_excerpt:
                                articles_list += f"\n   可引用摘录：{normalized_excerpt}"

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

    async def _get_source_names(self) -> dict[int, str]:
        repo = SourceRepository(self.db)
        try:
            sources = await repo.fetch_many(limit=5000, offset=0, order_by="id ASC")
        except Exception:
            return {}
        return {item["id"]: item.get("site_name", f"Source {item['id']}") for item in sources if item.get("id") is not None}

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
            section_templates = self._default_section_templates("综合新闻研究报告")

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
        overview = (
            f"本报告覆盖 {report.time_range_start.strftime('%Y-%m-%d')} 至 "
            f"{report.time_range_end.strftime('%Y-%m-%d')} 的新闻材料，并于 "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 生成。"
            f"本轮分析共处理 {statistics.get('total_articles', 0)} 篇文章，"
            f"去重后形成 {statistics.get('clustered_articles', 0)} 个核心新闻簇，"
            f"最终抽取 {statistics.get('event_count', 0)} 个重点事件作为主分析对象。"
            "下文将围绕这些证据材料，按照研究报告而非新闻快讯的方式展开论证。"
        )

        header = f"""# {report.title}

## 报告说明

{overview}

---

"""

        # 合并板块
        sections_content = ""
        for section in sections:
            sections_content += f"\n## {section['title']}\n\n"
            sections_content += section['content']
            sections_content += "\n\n---\n\n"

        events_paragraphs = []
        for event in events:
            events_paragraphs.append(
                f"“{event['event_title']}”是本期识别出的重点议题之一。"
                f"该事件涉及 {event['article_count']} 篇相关文章，"
                f"其核心摘要为：{event['event_summary']}。"
                f"模型在聚类与排序后为其赋予的重要性分值为 {event['importance_score']:.2f}，"
                f"相关关键词包括 {', '.join(event['keywords'][:5])}。"
            )
        events_content = "\n## 核心事件说明\n\n" + "\n\n".join(events_paragraphs)

        references_content = self._build_references_section()

        draft = header + sections_content + events_content + "\n\n---\n\n" + references_content
        return await self._polish_full_report(
            draft=draft,
            report=report,
            events=events,
            statistics=statistics,
        )

    def _build_references_section(self) -> str:
        if not self.reference_manager.references:
            return "## 参考文献\n\n本报告未记录到可用参考文献。"

        lines = ["## 参考文献", ""]
        for index, ref in enumerate(self.reference_manager.references.values(), 1):
            published = ref.publish_time.strftime("%Y-%m-%d %H:%M") if isinstance(ref.publish_time, datetime) else str(ref.publish_time or "未知时间")
            source_name = ref.source_name or "未知来源"
            author = f"{ref.author}." if ref.author else ""
            lines.append(
                f"[{index}] {author} [{ref.title}]({ref.url}). {source_name}. 发布时间：{published}."
            )
            lines.append("")
        return "\n".join(lines)

    async def _polish_full_report(
        self,
        *,
        draft: str,
        report: Report,
        events: list[dict[str, Any]],
        statistics: dict[str, int],
    ) -> str:
        if not self._report_needs_polish(draft):
            return draft

        evidence_context = await self._build_events_context_with_articles_and_images(events)
        current = draft
        for attempt in range(2):
            logger.info(f"最终报告触发统一润色重写，第 {attempt + 1} 次")
            prompt = (
                f"请将下面这份报告草稿重写为成熟研究机构风格的最终版本，标题是《{report.title}》。\n\n"
                "必须满足以下条件：\n"
                "1. 除“参考文献”部分外，正文全部使用长段落 prose，不要使用项目符号、编号列表、"
                "“一、二、三”或“首先、其次、最后”式提纲表达。\n"
                "2. 每个核心判断必须保留或补上引用标记 [1][2]。\n"
                "3. 段落必须充分展开，不能短句堆砌；要有背景、因果、立场、影响和不确定性分析。\n"
                "4. 保留现有章节结构，但把语言改成真正的研究报告风格。\n"
                "5. 最后的“参考文献”部分必须采用 Markdown 可点击链接格式，例如 [标题](https://...)。\n"
                "6. 不要添加草稿里没有依据的新事实。\n"
                "7. 如果草稿里有列表句式，必须全部改写成自然段，不允许残留。\n\n"
                "统计信息：\n"
                f"文章总数={statistics.get('total_articles', 0)}，"
                f"去重后事件簇={statistics.get('clustered_articles', 0)}，"
                f"重点事件={statistics.get('event_count', 0)}。\n\n"
                "可用证据摘要：\n"
                f"{evidence_context}\n\n"
                "草稿如下：\n"
                f"{current}\n\n"
                "请直接输出重写后的完整报告。"
            )

            polished = ""
            try:
                async for chunk in self.ai_client.chat(
                    user_message=prompt,
                    system_prompt=(
                        "你是一位国际事务研究机构的主笔作者。你的任务是把现有草稿改写成"
                        "完整、厚重、带引用、带来源链接的高质量研究报告。"
                    ),
                ):
                    polished += chunk
            except Exception as exc:
                logger.error(f"最终报告润色失败: {exc}", exc_info=True)
                return current

            if polished:
                current = polished
            if not self._report_needs_polish(current):
                return current
        return current

    def _report_needs_polish(self, draft: str) -> bool:
        text = (draft or "").strip()
        if not text:
            return True
        if "## 参考文献" not in text:
            return True
        if len(re.findall(r"\[\d+\]", text)) < 6:
            return True
        body_without_refs = text.split("## 参考文献", 1)[0]
        if re.search(r"(?m)^\s*[-*•]\s+", body_without_refs):
            return True
        if re.search(r"(?m)^\s*\d+[.)]\s+", body_without_refs):
            return True
        if re.search(r"(?m)^\s*[一二三四五六七八九十]+[、.]", body_without_refs):
            return True
        if re.search(r"首先|其次|再次|最后", body_without_refs):
            return True
        if "](http" not in text:
            return True
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body_without_refs) if p.strip() and not p.strip().startswith("#")]
        if paragraphs and sum(1 for p in paragraphs if len(p) < 260) >= max(2, len(paragraphs) // 3):
            return True
        if paragraphs and sum(1 for p in paragraphs if len(p) < 180) >= max(3, len(paragraphs) // 2):
            return True
        return False
