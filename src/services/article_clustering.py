"""
文章聚类和去重服务
使用 SimHash 进行高效的文本聚类和去重
"""

import jieba
import logging
from collections import defaultdict
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.repository.article_repository import ArticleRepository
from src.services.aggregator import InfluenceScorer
from src.services.simhash import TextCluster


logger = logging.getLogger(__name__)


def extract_keywords_from_prompt(text: str, top_k: int = 10) -> list[str]:
    """
    从用户输入中提取关键字

    Args:
        text: 用户输入的文本
        top_k: 返回前K个关键字

    Returns:
        关键字列表
    """
    if not text:
        return []

    # 使用 jieba 提取关键词
    words = jieba.cut(text)
    # 过滤停用词和短词
    stopwords = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}

    keywords = []
    for word in words:
        word = word.strip()
        if len(word) >= 2 and word not in stopwords:
            keywords.append(word)

    # 去重并返回前 top_k 个
    return list(set(keywords))[:top_k]


class ArticleCluster:
    """文章聚类结果"""

    def __init__(
        self,
        representative_id: int,
        representative: dict[str, Any],
        duplicate_ids: list[int],
        duplicates: list[dict[str, Any]],
    ):
        self.representative_id = representative_id
        self.representative = representative
        self.duplicate_ids = duplicate_ids
        self.duplicates = duplicates

    @property
    def total_count(self) -> int:
        """聚类中文章总数"""
        return 1 + len(self.duplicates)


class ArticleClusteringService:
    """
    文章聚类服务
    负责文章的聚类、去重和代表性文章选择
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.article_repo = ArticleRepository(db)
        self.clusterer = TextCluster(
            simhash_bits=64,
            similarity_threshold=0.85,  # 相似度阈值
            token_type='word'
        )

    async def cluster_articles_by_timerange(
        self,
        start_date,
        end_date,
        language: str = "zh",
        keywords: list[str] | None = None,
        min_score: float = 20.0,
    ) -> list[ArticleCluster]:
        """
        根据时间范围聚类文章

        Args:
            start_date: 开始时间
            end_date: 结束时间
            language: 语言筛选（zh=中文, kk=哈萨克语）
            keywords: 用户输入的关键字列表（用于评分筛选）
            min_score: 最低分数阈值（低于此分数的文章将被过滤）

        Returns:
            文章聚类列表
        """
        logger.info(f"开始聚类文章：{start_date} 到 {end_date}")

        # 获取时间范围内的所有文章
        articles = await self.article_repo.fetch_by_timerange(
            start_date=start_date,
            end_date=end_date,
            language=language
        )

        if not articles:
            logger.warning("没有找到符合条件的文章")
            return []

        logger.info(f"找到 {len(articles)} 篇文章")

        # 如果提供了关键字，使用评分器进行筛选
        if keywords:
            scorer = InfluenceScorer()
            scored_articles = []

            for article in articles:
                # 转换为字典以支持赋值
                article_dict = dict(article)
                score = scorer.calculate_score(article_dict, keywords=keywords)
                article_dict['_score'] = score

                # 只保留分数高于阈值的文章
                if score >= min_score:
                    scored_articles.append(article_dict)

            logger.info(f"关键字筛选: {len(scored_articles)}/{len(articles)} 篇文章通过阈值 ({min_score}分)")

            # 按分数排序
            scored_articles.sort(key=lambda a: a['_score'], reverse=True)

            # 限制最多处理的文章数量
            articles = scored_articles[:1000]

            # 清理临时分数字段
            for article in articles:
                article.pop('_score', None)
        else:
            # 没有关键字时，也需要转换为字典
            articles = [dict(a) for a in articles]

        logger.info(f"实际处理 {len(articles)} 篇文章")

        # 准备文本和ID
        texts = []
        ids = []

        for article in articles:
            # 组合标题和内容用于聚类
            title = article.get("title", "")
            content = article.get("content", "")
            text = f"{title}\n{content}"

            texts.append(text)
            ids.append(article["id"])

        # 执行聚类
        cluster_map = self.clusterer.cluster_texts(texts, ids)

        # 构建聚类结果
        clusters = []

        for rep_id, duplicate_ids in cluster_map.items():
            # 找到代表文章
            representative = next((a for a in articles if a["id"] == rep_id), None)
            if not representative:
                continue

            # 找到重复文章
            duplicates = [a for a in articles if a["id"] in duplicate_ids]

            # 选择最具代表性的文章（内容最长的）
            all_articles = [representative] + duplicates
            representative = max(all_articles, key=lambda x: len(x.get("content") or ""))

            # 更新代表ID
            rep_id = representative["id"]

            # 重新计算重复ID列表（排除代表ID）
            duplicate_ids = [a["id"] for a in all_articles if a["id"] != rep_id]
            duplicates = [a for a in all_articles if a["id"] != rep_id]

            cluster = ArticleCluster(
                representative_id=rep_id,
                representative=representative,
                duplicate_ids=duplicate_ids,
                duplicates=duplicates,
            )
            clusters.append(cluster)

        # 按聚类大小排序（大的在前）
        clusters.sort(key=lambda c: c.total_count, reverse=True)

        logger.info(f"聚类完成：{len(clusters)} 个聚类，去重后 {len(clusters)} 篇代表性文章")

        return clusters

    async def deduplicate_articles(
        self,
        articles: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[int, list[int]]]:
        """
        去重文章列表

        Args:
            articles: 文章列表

        Returns:
            (去重后的文章列表, {代表ID: [重复ID列表]})
        """
        if not articles:
            return [], {}

        # 准备文本和ID
        texts = []
        ids = []

        for article in articles:
            title = article.get("title", "")
            content = article.get("content", "")
            text = f"{title}\n{content}"

            texts.append(text)
            ids.append(article["id"])

        # 执行聚类
        cluster_map = self.clusterer.cluster_texts(texts, ids)

        # 选择代表文章（每个聚类选内容最长的）
        deduplicated = []
        duplicate_map = {}

        for rep_id, duplicate_ids in cluster_map.items():
            # 获取聚类中的所有文章
            cluster_articles = [
                a for a in articles
                if a["id"] == rep_id or a["id"] in duplicate_ids
            ]

            # 选择最长的作为代表
            representative = max(cluster_articles, key=lambda x: len(x.get("content") or ""))

            # 获取实际重复的ID列表
            actual_duplicates = [
                a["id"] for a in cluster_articles
                if a["id"] != representative["id"]
            ]

            deduplicated.append(representative)
            duplicate_map[representative["id"]] = actual_duplicates

        return deduplicated, duplicate_map

    def calculate_cluster_importance(
        self,
        cluster: ArticleCluster,
    ) -> float:
        """
        计算聚类的重要性分数

        Args:
            cluster: 文章聚类

        Returns:
            重要性分数（0-1）
        """
        # 因素1：聚类大小（文章数量）
        size_score = min(cluster.total_count / 10, 1.0)

        # 因素2：内容长度
        content_length = len(cluster.representative.get("content") or "")
        length_score = min(content_length / 2000, 1.0)

        # 因素3：来源权威性（假设源ID越小越权威）
        source_id = cluster.representative.get("source_id", 999)
        source_score = max(1.0 - (source_id / 100), 0.1)

        # 综合分数（加权平均）
        importance = (
            size_score * 0.5 +
            length_score * 0.3 +
            source_score * 0.2
        )

        return importance
