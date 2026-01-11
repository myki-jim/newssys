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
    支持基于 AI 生成的关键词进行相关性筛选和评分
    """

    def __init__(self):
        self.extractor = EventExtractor()

    def _calculate_keyword_relevance(
        self,
        event_info: dict[str, Any],
        ai_keywords: list[str],
    ) -> float:
        """
        计算事件与 AI 生成关键词的匹配度

        Args:
            event_info: 事件信息（包含从聚类中提取的关键词）
            ai_keywords: AI 生成的关键词列表

        Returns:
            关键词匹配度分数 (0-1)
        """
        if not ai_keywords:
            return 0.5  # 无关键词时给予中等分数

        event_keywords = event_info.get("keywords", [])
        if not event_keywords:
            return 0.0

        # 计算匹配度
        matched_count = 0
        partial_match_count = 0

        ai_keywords_lower = [kw.lower() for kw in ai_keywords]
        event_keywords_lower = [kw.lower() for kw in event_keywords]

        for ai_kw in ai_keywords_lower:
            # 完全匹配
            if ai_kw in event_keywords_lower:
                matched_count += 1
            # 部分匹配（AI关键词包含事件关键词的一部分）
            else:
                for event_kw in event_keywords_lower:
                    if ai_kw in event_kw or event_kw in ai_kw:
                        partial_match_count += 1
                        break

        # 完全匹配权重更高
        total_keywords = len(ai_keywords)
        if total_keywords == 0:
            return 0.0

        relevance_score = (
            (matched_count * 1.0 + partial_match_count * 0.5) / total_keywords
        )

        return min(relevance_score, 1.0)

    def _calculate_keyword_relevance_from_articles(
        self,
        all_articles: list[dict[str, Any]],
        ai_keywords: list[str],
    ) -> float:
        """
        从文章内容计算与 AI 关键词的匹配度

        Args:
            all_articles: 聚类中的所有文章
            ai_keywords: AI 生成的关键词列表

        Returns:
            关键词匹配度分数 (0-1)
        """
        if not ai_keywords:
            return 0.5

        # 合并所有文章的标题和内容
        all_text = ""
        for article in all_articles:
            title = article.get("title", "") or ""
            content = article.get("content", "") or ""
            all_text += title + " " + content[:500] + " "

        all_text_lower = all_text.lower()

        # 统计关键词出现次数
        match_count = 0
        for keyword in ai_keywords:
            if keyword.lower() in all_text_lower:
                match_count += 1

        return match_count / len(ai_keywords)

    async def select_top_events(
        self,
        clusters: list,  # list[ArticleCluster]
        max_events: int = 20,
        ai_keywords: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        选择最重要的 N 个事件（支持基于 AI 关键词的筛选和评分）

        Args:
            clusters: 文章聚类列表
            max_events: 最大事件数量（用户设置的封顶值）
            ai_keywords: AI 生成的关键词列表（可选）

        Returns:
            事件列表（按重要性排序）
            注意：最少返回 15 个事件，最多返回 max_events 个事件
        """
        # 确保至少返回 15 个事件，最多返回用户设置的 max_events
        actual_max_events = max(15, max_events)
        logger.info(f"事件数量设置：用户设置={max_events}，实际使用={actual_max_events}（最少15个）")
        events = []
        filtered_clusters = []

        # 第一层：使用关键词过滤相关聚类
        if ai_keywords:
            logger.info(f"使用 AI 生成的 {len(ai_keywords)} 个关键词进行筛选")
            for cluster in clusters:
                # 从聚类内容计算关键词匹配度
                all_articles = [cluster.representative] + cluster.duplicates
                relevance = self._calculate_keyword_relevance_from_articles(
                    all_articles, ai_keywords
                )
                # 只保留匹配度大于阈值的聚类
                if relevance >= 0.2:  # 至少20%的匹配度
                    filtered_clusters.append((cluster, relevance))
                else:
                    logger.debug(f"聚类匹配度 {relevance:.2f} < 0.2，已过滤")
        else:
            filtered_clusters = [(cluster, 0.5) for cluster in clusters]

        logger.info(f"关键词筛选后剩余 {len(filtered_clusters)} 个聚类（原始 {len(clusters)} 个）")

        for cluster, initial_relevance in filtered_clusters:
            # 获取聚类中的所有文章
            all_articles = [cluster.representative] + cluster.duplicates

            # 提取事件
            event_info = self.extractor.extract_event_from_cluster(
                cluster_title=cluster.representative.get("title", ""),
                cluster_articles=all_articles,
            )

            # 计算词频评分（原始 importance）
            content_length = sum(
                len(a.get("content") or "")
                for a in all_articles
            )

            tfidf_importance = self.extractor.calculate_event_importance(
                event=event_info,
                cluster_size=cluster.total_count,
                content_length=content_length,
            )

            # 计算关键词匹配度
            keyword_relevance = self._calculate_keyword_relevance(
                event_info, ai_keywords or []
            )

            # 混合评分：词频评分 60% + 关键词匹配度 40%
            if ai_keywords:
                combined_importance = tfidf_importance * 0.6 + keyword_relevance * 0.4
            else:
                combined_importance = tfidf_importance

            events.append({
                **event_info,
                "article_count": cluster.total_count,
                "content_length": content_length,
                "importance": combined_importance,  # 统一字段名为 importance
                "importance_score": combined_importance,  # 保持兼容性
                "tfidf_score": tfidf_importance,  # 词频评分
                "keyword_relevance": keyword_relevance,  # 关键词匹配度
                "representative_article_id": cluster.representative_id,
                "article_ids": [cluster.representative_id] + cluster.duplicate_ids,
            })

            logger.debug(
                f"事件 '{event_info['event_title'][:30]}...': "
                f"TF-IDF={tfidf_importance:.2f}, "
                f"关键词匹配={keyword_relevance:.2f}, "
                f"综合={combined_importance:.2f}"
            )

        # 按混合重要性排序并取前 N 个
        events.sort(key=lambda e: e["importance_score"], reverse=True)
        top_events = events[:actual_max_events]

        logger.info(
            f"从 {len(clusters)} 个聚类中选择了 {len(top_events)} 个重点事件 "
            f"(关键词筛选后 {len(filtered_clusters)} 个，用户上限={max_events})"
        )

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
