"""
内容压缩器
将长文本压缩为适合 AI 处理的摘要
"""

import re
from typing import Any


class ContentCompressor:
    """
    内容压缩器
    智能压缩长文本，保留关键信息
    """

    # 最大长度配置
    MAX_TITLE_LENGTH = 100
    MAX_SUMMARY_LENGTH = 500
    MAX_FULL_LENGTH = 3000

    def __init__(
        self,
        max_summary_length: int = MAX_SUMMARY_LENGTH,
        max_full_length: int = MAX_FULL_LENGTH,
    ) -> None:
        """
        初始化压缩器

        Args:
            max_summary_length: 最大摘要长度
            max_full_length: 最大完整长度
        """
        self.max_summary_length = max_summary_length
        self.max_full_length = max_full_length

    def compress_article(
        self,
        article: dict[str, Any],
        mode: str = 'summary',
    ) -> dict[str, Any]:
        """
        压缩文章内容

        Args:
            article: 文章数据字典
            mode: 压缩模式 ('summary', 'full', 'title_only')

        Returns:
            压缩后的文章字典
        """
        compressed = {
            'id': article.get('id'),
            'url': article.get('url'),
            'title': self._compress_title(article.get('title', '')),
            'publish_time': article.get('publish_time'),
            'source_id': article.get('source_id'),
            'original_length': len(article.get('content', '')),
        }

        if mode == 'title_only':
            compressed['content'] = None
        elif mode == 'summary':
            compressed['content'] = self._compress_to_summary(
                article.get('content', '')
            )
            compressed['compressed_length'] = len(compressed['content'] or '')
        else:  # full
            compressed['content'] = self._compress_to_full(
                article.get('content', '')
            )
            compressed['compressed_length'] = len(compressed['content'] or '')

        return compressed

    def _compress_title(self, title: str) -> str:
        """压缩标题"""
        if not title:
            return 'Untitled'

        title = title.strip()

        if len(title) <= self.MAX_TITLE_LENGTH:
            return title

        # 截断并添加省略号
        return title[:self.MAX_TITLE_LENGTH - 3] + '...'

    def _compress_to_summary(self, content: str) -> str | None:
        """
        压缩为摘要
        保留第一段和关键句子
        """
        if not content:
            return None

        # 移除 Markdown 格式
        content = self._strip_markdown(content)

        # 分段
        paragraphs = self._split_paragraphs(content)

        if not paragraphs:
            return None

        # 保留第一段
        summary = paragraphs[0]

        # 如果第一段太长，截断
        if len(summary) > self.max_summary_length:
            summary = summary[:self.max_summary_length - 3] + '...'

        return summary.strip()

    def _compress_to_full(self, content: str) -> str | None:
        """
        压缩为完整内容（但限制长度）
        保留前几段
        """
        if not content:
            return None

        # 移除 Markdown 格式
        content = self._strip_markdown(content)

        # 分段
        paragraphs = self._split_paragraphs(content)

        if not paragraphs:
            return None

        # 保留前几段
        result_parts = []
        current_length = 0

        for para in paragraphs:
            if current_length + len(para) > self.max_full_length:
                break
            result_parts.append(para)
            current_length += len(para)

        result = '\n\n'.join(result_parts)

        if current_length >= self.max_full_length:
            result = result[:self.max_full_length - 3] + '...'

        return result.strip()

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """移除 Markdown 格式"""
        if not text:
            return ''

        # 移除链接
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # 移除加粗
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        # 移除斜体
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        # 移除标题
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        # 移除代码块
        text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # 移除引用
        text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
        # 移除列表标记
        text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)

        return text

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        """分段"""
        if not text:
            return []

        # 按双换行分段
        paragraphs = re.split(r'\n\s*\n', text.strip())

        # 过滤空段落
        return [p.strip() for p in paragraphs if p.strip()]

    def compress_batch(
        self,
        articles: list[dict[str, Any]],
        mode: str = 'summary',
    ) -> list[dict[str, Any]]:
        """
        批量压缩文章

        Args:
            articles: 文章列表
            mode: 压缩模式

        Returns:
            压缩后的文章列表
        """
        return [
            self.compress_article(article, mode=mode)
            for article in articles
        ]

    def calculate_compression_stats(
        self,
        original_articles: list[dict[str, Any]],
        compressed_articles: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        计算压缩统计

        Args:
            original_articles: 原始文章列表
            compressed_articles: 压缩后的文章列表

        Returns:
            压缩统计信息
        """
        total_original = sum(
            len(a.get('content', ''))
            for a in original_articles
        )

        total_compressed = sum(
            a.get('compressed_length', 0)
            for a in compressed_articles
        )

        return {
            'original_size': total_original,
            'compressed_size': total_compressed,
            'compression_ratio': total_compressed / total_original if total_original > 0 else 0,
            'article_count': len(original_articles),
            'average_original_size': total_original / len(original_articles) if original_articles else 0,
            'average_compressed_size': total_compressed / len(compressed_articles) if compressed_articles else 0,
        }


class ContextBuilder:
    """
    上下文构建器
    将压缩后的文章组装成适合 AI 的上下文格式
    """

    def __init__(
        self,
        compressor: ContentCompressor | None = None,
    ) -> None:
        """
        初始化上下文构建器

        Args:
            compressor: 内容压缩器
        """
        self.compressor = compressor or ContentCompressor()

    def build_prompt_context(
        self,
        articles: list[dict[str, Any]],
        mode: str = 'summary',
        include_metadata: bool = True,
    ) -> str:
        """
        构建 AI 上下文

        Args:
            articles: 文章列表
            mode: 压缩模式
            include_metadata: 是否包含元数据

        Returns:
            格式化的上下文字符串
        """
        # 压缩文章
        compressed = self.compressor.compress_batch(articles, mode=mode)

        # 构建上下文
        sections = []

        for i, article in enumerate(compressed, 1):
            section = f"## Article {article['id']}\n\n"
            section += f"**Title**: {article['title']}\n\n"

            if include_metadata:
                if article.get('publish_time'):
                    section += f"**Published**: {article['publish_time']}\n"
                if article.get('source_id'):
                    section += f"**Source ID**: {article['source_id']}\n"
                section += f"**URL**: {article['url']}\n"

            section += f"\n{article['content'] or '(No content)'}\n"
            sections.append(section)

        return '\n\n---\n\n'.join(sections)

    def build_summary_list(
        self,
        articles: list[dict[str, Any]],
    ) -> str:
        """
        构建摘要列表
        用于快速浏览
        """
        lines = ["## Article Summary List\n\n"]

        for i, article in enumerate(articles, 1):
            title = article.get('title', 'Untitled')
            url = article.get('url', '')
            pub_time = article.get('publish_time')

            line = f"{i}. **{title}**"
            if pub_time:
                line += f" ({pub_time.strftime('%Y-%m-%d')})"
            line += f"\n   URL: {url}\n"

            lines.append(line)

        return '\n'.join(lines)

    def estimate_token_count(self, text: str) -> int:
        """
        估算 Token 数量
        粗略估算：中文约 1.5 字符/token，英文约 4 字符/token
        """
        # 统计中文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        # 统计非中文字符
        other_chars = len(text) - chinese_chars

        # 估算
        chinese_tokens = chinese_chars / 1.5
        other_tokens = other_chars / 4

        return int(chinese_tokens + other_tokens)
