"""
文章聚类和去重服务
使用 SimHash 进行高效的文本聚类和去重
"""

import jieba
import inspect
import logging
import re
from datetime import datetime, timezone
from typing import Any
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.repository.article_repository import ArticleRepository
from src.services.aggregator import InfluenceScorer
from src.services.simhash import TextCluster, normalize_text, text_similarity_simple, tokenize_mixed_text


logger = logging.getLogger(__name__)

MAX_CLUSTER_ARTICLES = 400
MAX_BUCKET_TOKENS = 6
CLUSTER_PROGRESS_LOG_INTERVAL = 25


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

    # 去重并保留出现顺序
    unique_keywords = list(dict.fromkeys(keywords))
    return unique_keywords[:top_k]


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
            similarity_threshold=0.82,  # 新闻正文相对宽松的相似度阈值
            token_type='word'
        )

    @staticmethod
    def _build_cluster_text(article: dict[str, Any]) -> str:
        """构造用于聚类的文本，降低模板噪声影响。"""
        title = normalize_text(article.get("title", ""))
        content = normalize_text(article.get("content", ""))
        content = re.sub(r"\s+", " ", content)

        # 标题权重更高；正文只取前部有效内容，避免模板尾巴主导 hash。
        body = content[:1500]
        return f"{title}\n{title}\n{body}".strip()

    def _representative_score(self, article: dict[str, Any]) -> float:
        """选择代表文章时的综合评分。"""
        content = normalize_text(article.get("content", ""))
        title = normalize_text(article.get("title", ""))

        content_score = min(len(content) / 1200, 1.0) * 35
        title_score = min(len(title) / 30, 1.0) * 20
        source_bonus = max(15 - (article.get("source_id", 999) / 10), 0)
        keyword_score = float(article.get("_score", 0)) * 0.3

        publish_time = article.get("publish_time") or article.get("created_at")
        recency_score = 0.0
        if publish_time:
            if isinstance(publish_time, str):
                try:
                    publish_time = datetime.fromisoformat(publish_time.replace("Z", "+00:00"))
                except ValueError:
                    publish_time = None
            if publish_time:
                if publish_time.tzinfo is None:
                    publish_time = publish_time.replace(tzinfo=timezone.utc)
                age_hours = max((datetime.now(timezone.utc) - publish_time.astimezone(timezone.utc)).total_seconds() / 3600, 0)
                recency_score = max(20 - min(age_hours / 12, 20), 0)

        return content_score + title_score + source_bonus + keyword_score + recency_score

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        """解析时间字段。"""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None

    def _are_duplicates(
        self,
        article_a: dict[str, Any],
        article_b: dict[str, Any],
        hash_a: int,
        hash_b: int,
    ) -> bool:
        """
        判断两篇文章是否应视为转载/重复，而不是同主题不同进展。
        """
        title_a = normalize_text(article_a.get("title", ""))
        title_b = normalize_text(article_b.get("title", ""))
        body_a = normalize_text(article_a.get("content", ""))[:2000]
        body_b = normalize_text(article_b.get("content", ""))[:2000]

        title_similarity = text_similarity_simple(title_a, title_b)
        body_similarity = text_similarity_simple(body_a, body_b)
        simhash_similarity = self.clusterer.simhash.similarity(hash_a, hash_b)
        shared_tokens = (
            set(tokenize_mixed_text(f"{title_a} {body_a}"))
            & set(tokenize_mixed_text(f"{title_b} {body_b}"))
        )
        meaningful_shared_tokens = {token for token in shared_tokens if len(token) >= 2}

        dt_a = self._parse_dt(article_a.get("publish_time") or article_a.get("created_at"))
        dt_b = self._parse_dt(article_b.get("publish_time") or article_b.get("created_at"))
        time_gap_hours = None
        if dt_a and dt_b:
            time_gap_hours = abs((dt_a - dt_b).total_seconds()) / 3600

        # 标题几乎一致且正文高度相似，基本可以判为转载。
        if title_similarity >= 0.92 and (body_similarity >= 0.55 or simhash_similarity >= 0.86):
            return True

        # 不同媒体改写但正文核心事实高度接近，视为同一事件簇。
        if body_similarity >= 0.68 and simhash_similarity >= 0.8:
            if time_gap_hours is None or time_gap_hours <= 48:
                return True

        # 不同媒体改写较多时，退化到“共享关键实体/动作 + 正文中等相似 + 时间接近”。
        if body_similarity >= 0.5 and len(meaningful_shared_tokens) >= 4:
            if time_gap_hours is None or time_gap_hours <= 36:
                return True

        # 正文几乎一致，同时发布时间接近，也可视为重复分发。
        if body_similarity >= 0.78 and simhash_similarity >= 0.88:
            if time_gap_hours is None or time_gap_hours <= 72:
                return True

        # 标题和正文都中高相似，且时间接近，视为同一稿件的转载。
        if title_similarity >= 0.72 and body_similarity >= 0.6 and simhash_similarity >= 0.84:
            if time_gap_hours is None or time_gap_hours <= 48:
                return True

        return False

    def _candidate_bucket_keys(
        self,
        article: dict[str, Any],
        article_hash: int,
    ) -> list[str]:
        """
        为文章生成候选桶 key，减少无意义的两两比较。
        """
        title = normalize_text(article.get("title", ""))
        content = normalize_text(article.get("content", ""))[:600]
        publish_time = self._parse_dt(article.get("publish_time") or article.get("created_at"))

        title_tokens = [
            token for token in tokenize_mixed_text(title)
            if len(token) >= 2 and not token.isdigit()
        ]
        content_tokens = [
            token for token in tokenize_mixed_text(content)
            if len(token) >= 2 and not token.isdigit()
        ]

        ordered_tokens = list(dict.fromkeys(title_tokens + content_tokens))
        selected_tokens = ordered_tokens[:MAX_BUCKET_TOKENS]

        keys: list[str] = []
        if publish_time:
            day_key = publish_time.astimezone(timezone.utc).strftime("%Y%m%d")
            keys.append(f"day:{day_key}")
            for token in selected_tokens:
                keys.append(f"day:{day_key}:tok:{token}")

        for token in selected_tokens:
            keys.append(f"tok:{token}")

        title_prefix = title[:16].strip()
        if title_prefix:
            keys.append(f"title:{title_prefix}")

        # 保留一个粗粒度 hash 桶，用于标题改写较大的情况。
        keys.append(f"hash:{article_hash >> 56}")

        return list(dict.fromkeys(keys))

    async def _cluster_article_dicts(
        self,
        articles: list[dict[str, Any]],
        on_progress: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
    ) -> dict[int, list[int]]:
        """
        聚类文章，尽量只合并真实转载，避免把同事件不同进展误判为重复。
        """
        if not articles:
            return {}

        prepared = []
        for article in articles:
            cluster_text = self._build_cluster_text(article)
            article_hash = self.clusterer.compute_hash(cluster_text)
            prepared.append(
                {
                    "id": article["id"],
                    "article": article,
                    "hash": article_hash,
                    "keys": self._candidate_bucket_keys(article, article_hash),
                }
            )

        assigned: set[int] = set()
        clusters: dict[int, list[int]] = {}
        bucket_map: dict[str, list[int]] = {}
        total_candidates = len(prepared)
        total_comparisons = 0

        for index, item in enumerate(prepared):
            for key in item["keys"]:
                bucket_map.setdefault(key, []).append(index)

        for index, item in enumerate(prepared):
            if index % CLUSTER_PROGRESS_LOG_INTERVAL == 0 or index == total_candidates - 1:
                message = (
                    f"聚类进度: {index + 1}/{total_candidates}，"
                    f"已比较 {total_comparisons} 次，已形成 {len(clusters)} 个簇"
                )
                logger.info(message)
                if on_progress:
                    payload = {
                        "current": index + 1,
                        "total": total_candidates,
                        "comparisons": total_comparisons,
                        "cluster_count": len(clusters),
                        "message": message,
                    }
                    maybe_awaitable = on_progress(payload)
                    if inspect.isawaitable(maybe_awaitable):
                        await maybe_awaitable

            article_id = item["id"]
            if article_id in assigned:
                continue

            clusters[article_id] = []
            assigned.add(article_id)

            candidate_indexes: set[int] = set()
            for key in item["keys"]:
                for candidate_index in bucket_map.get(key, []):
                    if candidate_index > index:
                        candidate_indexes.add(candidate_index)

            for candidate_index in sorted(candidate_indexes):
                other = prepared[candidate_index]
                other_id = other["id"]
                if other_id in assigned:
                    continue

                total_comparisons += 1

                if self._are_duplicates(
                    item["article"],
                    other["article"],
                    item["hash"],
                    other["hash"],
                ):
                    clusters[article_id].append(other_id)
                    assigned.add(other_id)

        return clusters

    async def cluster_articles_by_timerange(
        self,
        start_date,
        end_date,
        language: str = "zh",
        keywords: list[str] | None = None,
        min_score: float = 20.0,
        on_progress: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
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
            if len(scored_articles) > MAX_CLUSTER_ARTICLES:
                logger.info(
                    "聚类候选过多，按相关性截断为 %s 篇（原始候选 %s 篇）",
                    MAX_CLUSTER_ARTICLES,
                    len(scored_articles),
                )
            articles = scored_articles[:MAX_CLUSTER_ARTICLES]

            # 清理临时分数字段
            for article in articles:
                article.pop('_score', None)
        else:
            # 没有关键字时，也需要转换为字典
            articles = [dict(a) for a in articles[:MAX_CLUSTER_ARTICLES]]
            if len(articles) == MAX_CLUSTER_ARTICLES:
                logger.info("未提供关键字，聚类候选截断为 %s 篇", MAX_CLUSTER_ARTICLES)

        logger.info(f"实际处理 {len(articles)} 篇文章")

        # 执行聚类
        cluster_map = await self._cluster_article_dicts(articles, on_progress=on_progress)

        # 构建聚类结果
        clusters = []

        for rep_id, duplicate_ids in cluster_map.items():
            # 找到代表文章
            representative = next((a for a in articles if a["id"] == rep_id), None)
            if not representative:
                continue

            # 找到重复文章
            duplicates = [a for a in articles if a["id"] in duplicate_ids]

            # 选择最具代表性的文章，而不是单纯选择最长文章。
            all_articles = [representative] + duplicates
            representative = max(all_articles, key=self._representative_score)

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

        # 执行聚类
        cluster_map = await self._cluster_article_dicts(articles)

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
            representative = max(cluster_articles, key=self._representative_score)

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
        content_length = len(normalize_text(cluster.representative.get("content") or ""))
        length_score = min(content_length / 2000, 1.0)

        # 因素3：相似文章间的一致性
        representative_text = self._build_cluster_text(cluster.representative)
        duplicate_similarities = [
            text_similarity_simple(representative_text, self._build_cluster_text(article))
            for article in cluster.duplicates[:5]
        ]
        consistency_score = (
            sum(duplicate_similarities) / len(duplicate_similarities)
            if duplicate_similarities else 0.5
        )

        # 综合分数（加权平均）
        importance = (
            size_score * 0.5 +
            length_score * 0.3 +
            consistency_score * 0.2
        )

        return importance
