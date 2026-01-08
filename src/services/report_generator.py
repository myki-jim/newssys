"""
灵活报告生成器
支持多模态输入、联网搜索和严格溯源的报告生成系统
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.aggregator import DataAggregator
from src.services.citation import ReferenceManager
from src.services.compressor import ContentCompressor, ContextBuilder
from src.services.search_engine import ContextEnricher, quick_search
from src.services.template import ReportTemplate, TemplateManager, template_manager


logger = logging.getLogger(__name__)


class AIModelInterface:
    """
    AI 模型接口
    定义与 AI 模型交互的抽象接口
    实际使用时需要替换为具体的 AI SDK 调用
    """

    @staticmethod
    async def generate(
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        """
        调用 AI 模型生成内容

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数
            max_tokens: 最大 token 数

        Returns:
            生成的文本
        """
        # TODO: 替换为实际的 AI SDK 调用
        # 示例代码（需要根据实际使用的 AI 服务调整）：
        #
        # from openai import AsyncOpenAI
        # client = AsyncOpenAI()
        # response = await client.chat.completions.create(
        #     model="gpt-4",
        #     messages=[
        #         {"role": "system", "content": system_prompt},
        #         {"role": "user", "content": user_prompt},
        #     ],
        #     temperature=temperature,
        #     max_tokens=max_tokens,
        # )
        # return response.choices[0].message.content

        # 临时返回示例内容
        return "[AI 生成的报告内容将在这里]"

    @staticmethod
    async def select_core_events(
        summaries: list[dict[str, Any]],
        limit: int = 20,
    ) -> list[int]:
        """
        使用 AI 选择核心事件

        Args:
            summaries: 文章摘要列表
            limit: 选择数量限制

        Returns:
            选中的文章 ID 列表
        """
        # TODO: 实现实际的 AI 选择
        # 这里可以返回一个简单实现
        summaries.sort(key=lambda s: s.get('score', 0), reverse=True)
        return [s['id'] for s in summaries[:limit]]


class ProReportGenerator:
    """
    专业报告生成器
    支持多种输入模式和完整的溯源机制
    """

    def __init__(
        self,
        session: AsyncSession,
        ai_model: AIModelInterface | None = None,
        enable_search: bool = True,
    ) -> None:
        """
        初始化报告生成器

        Args:
            session: 数据库会话
            ai_model: AI 模型接口
            enable_search: 是否启用联网搜索
        """
        self.session = session
        self.ai_model = ai_model or AIModelInterface()
        self.enable_search = enable_search

        # 初始化组件
        self.aggregator = DataAggregator(session)
        self.template_manager = template_manager
        self.compressor = ContentCompressor()
        self.context_builder = ContextBuilder(self.compressor)
        self.reference_manager = ReferenceManager()
        self.search_enricher = ContextEnricher() if enable_search else None

    async def generate_report(
        self,
        template_id: str | None = None,
        user_requirements: str | None = None,
        external_files: list[Path | str] | None = None,
        external_text: str | None = None,
        time_range: str = 'week',
        max_articles: int | None = None,
        enable_search: bool | None = None,
        search_query: str | None = None,
    ) -> dict[str, Any]:
        """
        生成报告
        支持多种输入模式

        Args:
            template_id: 模板 ID（可选）
            user_requirements: 用户自定义要求
            external_files: 外部文件路径列表
            external_text: 外部文本内容
            time_range: 时间范围
            max_articles: 最大文章数
            enable_search: 是否启用联网搜索
            search_query: 联网搜索关键词

        Returns:
            生成的报告结果
        """
        logger.info(f"Starting report generation (template={template_id})")

        # 确定是否启用搜索
        enable_search = enable_search if enable_search is not None else self.enable_search

        # 1. 获取模板配置
        template = None
        if template_id:
            template = self.template_manager.get_template(template_id)
            if template is None:
                raise ValueError(f"Template not found: {template_id}")

        # 2. 聚合本地数据
        if template:
            # 使用模板配置
            config = self.template_manager.get_template_config(template_id)
            articles = await self.aggregator.aggregate_core_events(
                time_range=config.get('time_range', time_range),
                source_ids=config.get('source_ids'),
                keywords=config.get('keywords'),
                ai_selector=self.ai_model.select_core_events,
            )
            max_articles = max_articles or config.get('max_articles', 20)
        else:
            # 使用默认配置
            articles = await self.aggregator.aggregate_core_events(
                time_range=time_range,
                ai_selector=self.ai_model.select_core_events,
            )
            max_articles = max_articles or 20

        articles = articles[:max_articles]

        logger.info(f"Aggregated {len(articles)} articles")

        # 3. 添加引用
        source_names = await self._get_source_names()
        for article in articles:
            source_id = article.get('source_id')
            source_name = source_names.get(source_id)
            self.reference_manager.add_reference(article, source_name=source_name)

        # 4. 处理外部输入
        external_context = ""
        if external_files:
            external_context = await self._process_external_files(external_files)

        if external_text:
            external_context += f"\n\n用户提供的文本：\n{external_text}\n"

        # 5. 联网搜索增强（可选）
        search_context = ""
        if enable_search and (search_query or (template and template.keywords)):
            query = search_query or " ".join(template.keywords[:3])
            search_context = await self._enrich_with_search(query, articles)

        # 6. 构建上下文
        context = self._build_full_context(articles, external_context, search_context)

        # 7. 构建提示词
        if template:
            system_prompt, user_prompt = self.template_manager.build_prompt(
                template_id,
                context=context,
                user_requirements=user_requirements,
            )
        else:
            system_prompt, user_prompt = self._build_default_prompts(
                context=context,
                user_requirements=user_requirements,
            )

        # 8. 调用 AI 生成
        logger.info("Calling AI model to generate report...")
        report_content = await self.ai_model.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # 9. 格式化报告（添加引用）
        final_report = self.reference_manager.format_report_with_citations(report_content)

        # 10. 验证引用
        validation = self.reference_manager.validate_citations(final_report)

        logger.info(f"Report generated. Citations valid: {validation['valid']}")

        return {
            'report': final_report,
            'template_id': template_id,
            'article_count': len(articles),
            'citations': self.reference_manager.export_json(),
            'citation_validation': validation,
            'generated_at': datetime.now().isoformat(),
        }

    async def _get_source_names(self) -> dict[int, str]:
        """获取源名称映射"""
        from src.repository.source_repository import SourceRepository

        source_repo = SourceRepository(self.session)
        sources = await source_repo.list_all()

        return {s['id']: s['site_name'] for s in sources}

    async def _process_external_files(
        self,
        files: list[Path | str],
    ) -> str:
        """
        处理外部文件

        Args:
            files: 文件路径列表

        Returns:
            文件内容组合
        """
        contents = []

        for file_path in files:
            path = Path(file_path)

            try:
                text = path.read_text(encoding='utf-8')

                # 根据文件类型处理
                if path.suffix.lower() in ['.md', '.markdown']:
                    contents.append(f"## 文件: {path.name}\n\n{text}")
                elif path.suffix.lower() == '.txt':
                    contents.append(f"## 文件: {path.name}\n\n{text}")
                else:
                    # 其他格式，作为纯文本处理
                    contents.append(f"## 文件: {path.name}\n\n{text}")

            except Exception as e:
                logger.error(f"Failed to read file {path}: {e}")

        return '\n\n---\n\n'.join(contents)

    async def _enrich_with_search(
        self,
        query: str,
        local_articles: list[dict[str, Any]],
    ) -> str:
        """
        使用联网搜索增强上下文

        Args:
            query: 搜索关键词
            local_articles: 本地文章

        Returns:
            搜索增强的上下文
        """
        if not self.search_enricher:
            return ""

        try:
            enrichment = await self.search_enricher.enrich_with_search(
                query=query,
                local_articles=local_articles,
                time_range='w',
                max_external_results=3,
            )

            return enrichment['combined_context']

        except Exception as e:
            logger.error(f"Search enrichment failed: {e}")
            return ""

    def _build_full_context(
        self,
        articles: list[dict[str, Any]],
        external_context: str,
        search_context: str,
    ) -> str:
        """
        构建完整的上下文

        Args:
            articles: 文章列表
            external_context: 外部内容
            search_context: 搜索上下文

        Returns:
            完整上下文字符串
        """
        sections = []

        # 本地数据摘要
        articles_summary = self.context_builder.build_summary_list(articles)
        sections.append("# 本地数据\n\n")
        sections.append(articles_summary)

        # 外部内容
        if external_context:
            sections.append("\n\n# 外部内容\n\n")
            sections.append(external_context)

        # 搜索结果
        if search_context:
            sections.append("\n\n# 联网搜索结果\n\n")
            sections.append(search_context)

        # 引用说明
        sections.append("\n\n# 引用说明\n\n")
        sections.append("请在报告中使用 [1], [2] 等格式标注引用，引用序号对应上述本地数据的文章顺序。")

        return '\n'.join(sections)

    def _build_default_prompts(
        self,
        context: str,
        user_requirements: str | None = None,
    ) -> tuple[str, str]:
        """
        构建默认提示词

        Args:
            context: 上下文
            user_requirements: 用户要求

        Returns:
            (system_prompt, user_prompt) 元组
        """
        system_prompt = """你是一位专业的新闻分析专家。你的任务是基于提供的材料生成高质量的分析报告。

报告要求：
1. 结构清晰，逻辑严谨
2. 分析深入，见解独到
3. 所有事实陈述必须使用引用标记 [1], [2] 等
4. 引用必须与提供的材料严格对应
5. 语言专业、准确、客观"""

        user_prompt = f"""请基于以下材料生成分析报告：

{context}"""

        if user_requirements:
            user_prompt = f"用户要求：\n{user_requirements}\n\n{user_prompt}"

        return system_prompt, user_prompt

    async def generate_quick_summary(
        self,
        article_ids: list[int],
    ) -> str:
        """
        快速生成摘要
        基于指定的文章 ID 列表

        Args:
            article_ids: 文章 ID 列表

        Returns:
            摘要文本
        """
        from src.repository.article_repository import ArticleRepository

        article_repo = ArticleRepository(self.session)

        articles = []
        for aid in article_ids:
            article = await article_repo.get_by_id(aid)
            if article:
                articles.append(article)
                self.reference_manager.add_reference(article)

        context = self.context_builder.build_prompt_context(articles, mode='summary')

        summary = await self.ai_model.generate(
            system_prompt="请生成一份简洁的新闻摘要，包含所有关键信息。",
            user_prompt=f"基于以下文章生成摘要：\n\n{context}",
        )

        return summary

    async def close(self) -> None:
        """关闭资源"""
        if self.search_enricher:
            await self.search_enricher.close()


# 报告输出示例
EXAMPLE_REPORT = """# 哈萨克斯坦政治周报

## 本周要闻摘要

本周哈萨克斯坦政治局势总体稳定，总统托卡耶夫签署了一系列重要法案，进一步推进政治体制改革 [1]。议会通过了新的反腐败法案，加强了对政府官员的监督机制 [2]。

## 政治动态分析

### 政治体制改革继续深化

托卡耶夫总统在本周签署了关于政党注册程序简化的新法案，这一举措将进一步促进多党制发展 [1]。分析人士认为，这是继去年宪法改革后的又一重要步骤，体现了政府持续推进政治现代化的决心 [3]。

### 反腐败斗争取得新进展

总检察长办公室本周宣布，前阿拉木图市长因贪污罪名被提起诉讼 [2]。此案件是近期反腐败行动的重要组成部分，显示了政府打击腐败的持续决心 [4]。

## 下周展望

预计下周议会将继续审议新的一年预算草案，教育和社会福利支出预计将是重点讨论议题 [5]。

## References

1. **托卡耶夫签署政党改革法案**
   来源: 哈萨克斯坦总统府官网
   发布时间: 2024-01-15 10:30
   链接: https://www.akorda.kz/...

2. **前阿拉木图市长被提起诉讼**
   来源: 哈萨克斯坦晚报
   发布时间: 2024-01-14 16:45
   链接: https://www.example.com/...

3. **政治改革持续推进**
   来源: 中亚观察
   发布时间: 2024-01-15 09:00
   链接: https://www.central-asia observer.org/...

4. **反腐败行动升级**
   来源: 哈萨克斯坦真理报
   发布时间: 2024-01-14 18:20
   链接: https://www.pravda.kz/...

5. **预算草案审议即将开始**
   来源: 哈萨克斯坦议会新闻
   发布时间: 2024-01-15 14:00
   链接: https://www.parlament.kz/...
"""
