"""
事件提取和关键词分析服务
从文章聚类中提取重点事件，使用 TF-IDF 和关键词提取算法
"""

import logging
import re
from collections import Counter, defaultdict
from typing import Any

import jieba
import jieba.analyse


logger = logging.getLogger(__name__)


class EventExtractor:
    """
    事件提取器
    从文章聚类中提取关键事件
    """

    def __init__(self):
        # 停用词
        self.stopwords = self._load_stopwords()

        # 关键词提取参数
        self.default_top_k = 10
        self.default_allow_pos = ('n', 'nr', 'ns', 'nt', 'nz', 'v', 'vn')

    def _load_stopwords(self) -> set[str]:
        """加载停用词表"""
        # 基础停用词
        stopwords = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
            '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
            '自己', '这', '年', '月', '日', '时', '分', '秒', '周', '月', '日',
            '可以', '但是', '因为', '所以', '如果', '虽然', '让', '给', '为',
        }

        # 添加常见的无意义词
        stopwords.update({
            '表示', '指出', '认为', '称', '据', '报道', '消息', '透露', '透露',
            '相关', '有关', '目前', '现在', '正在', '已经', '进行', '工作',
        })

        return stopwords

    def extract_keywords_tfidf(
        self,
        text: str,
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """
        使用 TF-IDF 提取关键词

        Args:
            text: 输入文本
            top_k: 返回前 k 个关键词

        Returns:
            [(关键词, 分数), ...]
        """
        if not text:
            return []

        # 使用 jieba 的 TF-IDF 实现
        keywords = jieba.analyse.extract_tags(
            text,
            topK=top_k,
            withWeight=True,
            allowPOS=self.default_allow_pos
        )

        # 过滤停用词
        filtered = [
            (word, score)
            for word, score in keywords
            if word not in self.stopwords and len(word) > 1
        ]

        return filtered

    def extract_keywords_textrank(
        self,
        text: str,
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """
        使用 TextRank 提取关键词

        Args:
            text: 输入文本
            top_k: 返回前 k 个关键词

        Returns:
            [(关键词, 分数), ...]
        """
        if not text:
            return []

        # 使用 jieba 的 TextRank 实现
        keywords = jieba.analyse.textrank(
            text,
            topK=top_k,
            withWeight=True,
            allowPOS=self.default_allow_pos
        )

        # 过滤停用词
        filtered = [
            (word, score)
            for word, score in keywords
            if word not in self.stopwords and len(word) > 1
        ]

        return filtered

    def extract_event_from_cluster(
        self,
        cluster_title: str,
        cluster_articles: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        从文章聚类中提取事件

        Args:
            cluster_title: 聚类标题（第一篇文章的标题）
            cluster_articles: 聚类中的文章列表

        Returns:
            事件信息
        """
        # 合并所有文章内容
        all_content = []
        for article in cluster_articles:
            title = article.get("title") or ""
            content = article.get("content") or ""
            if title:
                all_content.append(title)
            if content:
                # 只取前500字，避免内容过长
                all_content.append(content[:500])

        combined_text = "\n".join(all_content)

        # 提取关键词
        keywords_tfidf = self.extract_keywords_tfidf(combined_text, top_k=5)
        keywords_tr = self.extract_keywords_textrank(combined_text, top_k=5)

        # 合并两种方法的关键词
        keyword_scores = defaultdict(float)
        for word, score in keywords_tfidf:
            keyword_scores[word] += score * 0.6
        for word, score in keywords_tr:
            keyword_scores[word] += score * 0.4

        # 排序并取前5个
        top_keywords = sorted(keyword_scores.items(), key=lambda x: x[1], reverse=True)[:5]

        # 生成事件标题（使用最相关关键词）
        if top_keywords:
            main_keywords = [kw for kw, _ in top_keywords[:3]]
            event_title = f"{' · '.join(main_keywords)}"
        else:
            event_title = cluster_title[:50] if cluster_title else "未命名事件"

        # 生成事件摘要（从第一篇文章提取）
        first_article = cluster_articles[0]
        content = first_article.get("content") or ""
        if content:
            # 提取摘要（前200字）
            event_summary = content[:200].strip()
            if len(content) > 200:
                event_summary += "..."
        else:
            event_summary = cluster_title

        return {
            "event_title": event_title,
            "event_summary": event_summary,
            "keywords": [kw for kw, _ in top_keywords],
            "keyword_scores": dict(top_keywords),
        }

    def calculate_event_importance(
        self,
        event: dict[str, Any],
        cluster_size: int,
        content_length: int,
    ) -> float:
        """
        计算事件重要性分数

        Args:
            event: 事件信息
            cluster_size: 聚类大小（文章数量）
            content_length: 内容长度

        Returns:
            重要性分数（0-1）
        """
        # 因素1：聚类大小（文章数量越多越重要）
        size_score = min(cluster_size / 10, 1.0)

        # 因素2：内容长度
        length_score = min(content_length / 2000, 1.0)

        # 因素3：关键词分数（关键词权重越高越重要）
        keyword_scores = event.get("keyword_scores", {})
        if keyword_scores:
            avg_score = sum(keyword_scores.values()) / len(keyword_scores)
            keyword_score = min(avg_score / 0.5, 1.0)
        else:
            keyword_score = 0.5

        # 因素4：事件标题质量（关键词数量）
        keywords = event.get("keywords", [])
        title_quality_score = min(len(keywords) / 5, 1.0)

        # 综合分数（加权平均）
        importance = (
            size_score * 0.4 +
            length_score * 0.2 +
            keyword_score * 0.2 +
            title_quality_score * 0.2
        )

        return importance


class EventSelectionService:
    """
    事件选择服务
    从聚类结果中选择最重要的 N 个事件
    """

    def __init__(self):
        self.extractor = EventExtractor()

    async def select_top_events(
        self,
        clusters: list,  # list[ArticleCluster]
        max_events: int = 20,
    ) -> list[dict[str, Any]]:
        """
        选择最重要的 N 个事件

        Args:
            clusters: 文章聚类列表
            max_events: 最大事件数量

        Returns:
            事件列表（按重要性排序）
        """
        events = []

        for cluster in clusters:
            # 获取聚类中的所有文章
            all_articles = [cluster.representative] + cluster.duplicates

            # 提取事件
            event_info = self.extractor.extract_event_from_cluster(
                cluster_title=cluster.representative.get("title", ""),
                cluster_articles=all_articles,
            )

            # 计算重要性
            content_length = sum(
                len(a.get("content") or "")
                for a in all_articles
            )

            importance = self.extractor.calculate_event_importance(
                event=event_info,
                cluster_size=cluster.total_count,
                content_length=content_length,
            )

            events.append({
                **event_info,
                "article_count": cluster.total_count,
                "content_length": content_length,
                "importance": importance,  # 统一字段名为 importance
                "importance_score": importance,  # 保持兼容性
                "representative_article_id": cluster.representative_id,
                "article_ids": [cluster.representative_id] + cluster.duplicate_ids,
            })

        # 按重要性排序并取前 N 个
        events.sort(key=lambda e: e["importance_score"], reverse=True)
        top_events = events[:max_events]

        logger.info(f"从 {len(clusters)} 个聚类中选择了 {len(top_events)} 个重点事件")

        return top_events

    def generate_event_groups(
        self,
        events: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """
        将事件分组（按关键词相似度）

        Args:
            events: 事件列表

        Returns:
            分组后的事件字典
        """
        # 简单分组：按首关键词分组
        groups = defaultdict(list)

        for event in events:
            keywords = event.get("keywords", [])
            if keywords:
                main_keyword = keywords[0]
                groups[main_keyword].append(event)
            else:
                groups["其他"].append(event)

        return dict(groups)
