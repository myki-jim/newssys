"""
溯源管理系统
确保报告中的每个引用都能追溯到原始数据源
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Reference:
    """
    引用记录
    """

    id: int  # 文章 ID
    title: str
    url: str
    source_name: str | None = None
    publish_time: datetime | None = None
    author: str | None = None
    excerpt: str | None = None  # 引用的摘要片段

    # 追踪信息
    citation_count: int = 0  # 被引用次数
    first_cited_at: datetime | None = None  # 首次引用时间

    def to_markdown(self, index: int) -> str:
        """
        转换为 Markdown 格式

        Args:
            index: 引用序号

        Returns:
            Markdown 格式的引用条目
        """
        lines = [
            f"{index}. **{self.title}**",
        ]

        if self.author:
            lines.append(f"   作者: {self.author}")

        if self.source_name:
            lines.append(f"   来源: {self.source_name}")

        if self.publish_time:
            lines.append(f"   发布时间: {self.publish_time.strftime('%Y-%m-%d %H:%M')}")

        lines.append(f"   链接: {self.url}")

        if self.excerpt:
            lines.append(f"   引用内容: {self.excerpt[:100]}...")

        return '\n'.join(lines)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'source_name': self.source_name,
            'publish_time': self.publish_time.isoformat() if self.publish_time else None,
            'author': self.author,
            'excerpt': self.excerpt,
            'citation_count': self.citation_count,
        }


@dataclass
class CitationMarker:
    """
    引用标记
    用于在文本中标记引用位置
    """

    reference_id: int  # 引用的文章 ID
    position: int  # 在文本中的位置
    context: str  # 引用上下文


class ReferenceManager:
    """
    引用管理器
    负责管理报告中的所有引用
    """

    def __init__(self) -> None:
        """初始化引用管理器"""
        self.references: dict[int, Reference] = {}  # article_id -> Reference
        self.citation_markers: list[CitationMarker] = []
        self.next_index = 1  # 下一个引用序号

    def add_reference(
        self,
        article: dict[str, Any],
        source_name: str | None = None,
    ) -> int:
        """
        添加引用

        Args:
            article: 文章数据
            source_name: 来源名称（可选）

        Returns:
            引用序号
        """
        article_id = article.get('id')
        if article_id is None:
            raise ValueError("Article must have an 'id' field")

        # 如果已存在，增加引用计数
        if article_id in self.references:
            ref = self.references[article_id]
            ref.citation_count += 1
            return self._get_index_by_id(article_id)

        # 创建新引用
        ref = Reference(
            id=article_id,
            title=article.get('title', 'Untitled'),
            url=article.get('url', ''),
            source_name=source_name,
            publish_time=article.get('publish_time'),
            author=article.get('author'),
        )
        ref.citation_count = 1
        ref.first_cited_at = datetime.now()

        self.references[article_id] = ref

        index = self.next_index
        self.next_index += 1

        return index

    def add_citation_marker(
        self,
        reference_id: int,
        position: int,
        context: str,
    ) -> None:
        """
        添加引用标记

        Args:
            reference_id: 引用的文章 ID
            position: 位置
            context: 上下文
        """
        marker = CitationMarker(
            reference_id=reference_id,
            position=position,
            context=context,
        )
        self.citation_markers.append(marker)

    def get_index_by_id(self, article_id: int) -> int | None:
        """
        根据文章 ID 获取引用序号

        Args:
            article_id: 文章 ID

        Returns:
            引用序号，不存在返回 None
        """
        return self._get_index_by_id(article_id)

    def _get_index_by_id(self, article_id: int) -> int | None:
        """内部方法：获取引用序号"""
        if article_id not in self.references:
            return None

        # 引用序号从 1 开始，按添加顺序排列
        index = 1
        for ref_id in self.references.keys():
            if ref_id == article_id:
                return index
            index += 1

        return None

    def get_reference_by_index(self, index: int) -> Reference | None:
        """
        根据引用序号获取引用

        Args:
            index: 引用序号

        Returns:
            引用对象
        """
        if index < 1 or index > len(self.references):
            return None

        # 引用序号从 1 开始
        ref_list = list(self.references.values())
        return ref_list[index - 1]

    def get_reference_by_id(self, article_id: int) -> Reference | None:
        """
        根据文章 ID 获取引用

        Args:
            article_id: 文章 ID

        Returns:
            引用对象
        """
        return self.references.get(article_id)

    def generate_references_section(self) -> str:
        """
        生成参考文献部分

        Returns:
            Markdown 格式的参考文献
        """
        if not self.references:
            return "## References\n\nNo references cited."

        lines = ["## References\n\n"]

        for i, ref in enumerate(self.references.values(), 1):
            lines.append(ref.to_markdown(i))

        return '\n\n'.join(lines)

    def insert_citation_markers(
        self,
        text: str,
        article_id_to_index: dict[int, int] | None = None,
    ) -> str:
        """
        在文本中插入引用标记

        Args:
            text: 原始文本
            article_id_to_index: 文章 ID 到引用序号的映射（可选）

        Returns:
            带引用标记的文本

        注意：此方法需要 AI 生成的文本中包含特定的引用标记
        实际使用中，AI 应该在生成时直接添加 [1], [2] 等标记
        """
        # 如果已有引用标记，直接返回
        if re.search(r'\[\d+\]', text):
            return text

        # 如果没有映射，构建映射
        if article_id_to_index is None:
            article_id_to_index = {}
            for article_id, ref in self.references.items():
                index = self._get_index_by_id(article_id)
                if index:
                    article_id_to_index[article_id] = index

        # 这里只是示例，实际应用中需要在 AI 生成时就处理
        return text

    def format_report_with_citations(
        self,
        report_content: str,
    ) -> str:
        """
        格式化报告，添加引用部分

        Args:
            report_content: 报告内容

        Returns:
            完整的带引用的报告
        """
        # 确保引用标记格式正确
        formatted_content = self._normalize_citation_markers(report_content)

        # 添加参考文献部分
        references_section = self.generate_references_section()

        return f"{formatted_content}\n\n{references_section}"

    @staticmethod
    def _normalize_citation_markers(text: str) -> str:
        """
        标准化引用标记格式
        确保所有引用都是 [n] 格式
        """
        # 将 (1), (1), 1. 等格式统一为 [1]
        text = re.sub(r'\(\d+\)', lambda m: f'[{m.group(0)[1:-1]}]', text)
        text = re.sub(r'【\d+】', lambda m: f'[{m.group(0)[1:-1]}]', text)

        return text

    def validate_citations(self, text: str) -> dict[str, Any]:
        """
        验证引用的有效性

        Args:
            text: 报告文本

        Returns:
            验证结果
        """
        # 查找所有引用标记
        cited_indices = set(int(m.group(1)) for m in re.finditer(r'\[(\d+)\]', text))

        # 检查是否有超出范围的引用
        max_index = len(self.references)
        invalid_indices = cited_indices - set(range(1, max_index + 1))

        # 检查是否有未引用的参考文献
        all_indices = set(range(1, max_index + 1))
        uncited_indices = all_indices - cited_indices

        return {
            'valid': len(invalid_indices) == 0,
            'cited_count': len(cited_indices),
            'total_references': max_index,
            'invalid_indices': list(invalid_indices),
            'uncited_indices': list(uncited_indices),
        }

    def get_statistics(self) -> dict[str, Any]:
        """
        获取引用统计

        Returns:
            统计信息
        """
        return {
            'total_references': len(self.references),
            'total_citations': sum(ref.citation_count for ref in self.references.values()),
            'most_cited': max(self.references.values(), key=lambda r: r.citation_count, default=None),
            'citation_markers': len(self.citation_markers),
        }

    def export_json(self) -> dict[str, Any]:
        """
        导出为 JSON 格式

        Returns:
            JSON 数据
        """
        return {
            'references': [ref.to_dict() for ref in self.references.values()],
            'statistics': self.get_statistics(),
        }


class CitationParser:
    """
    引用解析器
    从 AI 生成的文本中解析引用信息
    """

    @staticmethod
    def extract_citation_indices(text: str) -> list[int]:
        """
        提取文本中的所有引用序号

        Args:
            text: 文本内容

        Returns:
            引用序号列表
        """
        matches = re.findall(r'\[(\d+)\]', text)
        return [int(m) for m in matches]

    @staticmethod
    def extract_citations_with_context(
        text: str,
        window_size: int = 50,
    ) -> list[dict[str, Any]]:
        """
        提取引用及其上下文

        Args:
            text: 文本内容
            window_size: 上下文窗口大小

        Returns:
            引用上下文列表
        """
        results = []

        for match in re.finditer(r'\[(\d+)\]', text):
            index = int(match.group(1))
            position = match.start()

            # 获取上下文
            start = max(0, position - window_size)
            end = min(len(text), position + window_size + len(match.group(0)))
            context = text[start:end].strip()

            results.append({
                'index': index,
                'position': position,
                'context': context,
            })

        return results

    @staticmethod
    def validate_consistency(
        text: str,
        reference_count: int,
    ) -> dict[str, Any]:
        """
        验证引用的一致性

        Args:
            text: 文本内容
            reference_count: 参考文献总数

        Returns:
            验证结果
        """
        cited_indices = CitationParser.extract_citation_indices(text)

        # 检查是否有超出范围的引用
        invalid = [i for i in cited_indices if i < 1 or i > reference_count]

        # 检查是否有连续的引用
        cited_set = set(cited_indices)
        missing = sorted(set(range(1, reference_count + 1)) - cited_set)

        return {
            'valid': len(invalid) == 0,
            'cited_indices': cited_indices,
            'invalid_indices': invalid,
            'missing_references': missing,
            'citation_count': len(cited_indices),
        }
