"""
海量数据聚合 Agent（优化版）
分片处理 + SimHash 聚类 + 优化的 AI Prompt
"""

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Article, ArticleStatus
from src.repository.article_repository import ArticleRepository
from src.services.simhash import TextCluster


logger = logging.getLogger(__name__)


class SourceWeight:
    """来源权重配置"""
    # 政府机构 / 官方媒体
    OFFICIAL = 1.0
    # 主流媒体
    MAINSTREAM = 0.8
    # 商业媒体
    COMMERCIAL = 0.6
    # 社交媒体 / 博客
    SOCIAL = 0.4
    # 未知来源
    UNKNOWN = 0.2


class InfluenceScorer:
    """
    影响力分数计算器
    公式：(关键字匹配 * 0.4) + (来源权重 * 0.3) + (热度 * 0.2) + (时效性 * 0.1)
    """

    def __init__(
        self,
        source_weights: dict[int, float] | None = None,
        default_weight: float = SourceWeight.UNKNOWN,
    ) -> None:
        """
        初始化影响力评分器

        Args:
            source_weights: 源 ID 到权重的映射
            default_weight: 默认权重
        """
        self.source_weights = source_weights or {}
        self.default_weight = default_weight

    def calculate_score(
        self,
        article: dict[str, Any],
        current_time: datetime | None = None,
        keywords: list[str] | None = None,
    ) -> float:
        """
        计算文章影响力分数

        Args:
            article: 文章数据字典
            current_time: 当前时间（默认为现在）
            keywords: 用户输入的关键字列表（用于匹配评分）

        Returns:
            影响力分数 (0-100)
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # 1. 关键字匹配分数 (0-100) - 主要影响因素
        keyword_score = self._calculate_keyword_match_score(article, keywords)

        # 2. 来源权重分数 (0-100)
        source_id = article.get('source_id', 0)
        source_weight = self.source_weights.get(source_id, self.default_weight)
        source_score = source_weight * 100

        # 3. 阅读量/热度分数 (0-100)
        popularity_score = self._calculate_popularity_score(article)

        # 4. 时效性分数 (0-100)
        publish_time = article.get('publish_time') or article.get('created_at')
        # 如果是字符串格式，转换为 datetime 对象
        if isinstance(publish_time, str):
            try:
                publish_time = datetime.fromisoformat(publish_time.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                publish_time = None
        recency_score = self._calculate_recency_score(publish_time, current_time)

        # 综合评分 - 关键字匹配是决定性因素
        final_score = (
            keyword_score * 0.65 +      # 关键字匹配：65% （主要因素）
            source_score * 0.15 +        # 来源权重：15%
            popularity_score * 0.15 +    # 热度：15%
            recency_score * 0.05         # 时效性：5%
        )

        return round(final_score, 2)

    def _calculate_keyword_match_score(
        self,
        article: dict[str, Any],
        keywords: list[str] | None = None,
    ) -> float:
        """
        计算关键字匹配分数
        匹配标题和内容中的关键字

        Args:
            article: 文章数据
            keywords: 用户输入的关键字列表

        Returns:
            匹配分数 (0-100)
        """
        if not keywords:
            # 没有关键字时，返回低分，避免不相关文章排名靠前
            return 5.0

        title = (article.get('title') or '').lower()
        content = (article.get('content') or '').lower()
        combined_text = f"{title} {content}"

        total_score = 0.0
        matched_count = 0

        for keyword in keywords:
            keyword_lower = keyword.lower()
            if not keyword_lower or len(keyword_lower) < 2:
                continue

            # 在标题中匹配（权重更高）
            if keyword_lower in title:
                # 标题完全匹配
                if keyword_lower == title:
                    total_score += 100
                    matched_count += 1
                # 标题包含关键字 - 检查是否是完整词而非部分
                else:
                    # 使用更严格的匹配：检查关键字是否作为完整词出现
                    # 检查是否是完整词匹配（前后有边界）
                    pattern = r'\b' + re.escape(keyword_lower) + r'\b'
                    if re.search(pattern, title):
                        total_score += 85
                    else:
                        total_score += 60  # 部分匹配分数较低
                    matched_count += 1

            # 在内容中匹配
            elif keyword_lower in content:
                # 计算出现次数
                occurrences = combined_text.count(keyword_lower)
                # 基础分降低 + 额外分（出现次数越多分数越高）
                content_score = min(20 + occurrences * 3, 40)
                total_score += content_score
                matched_count += 1

        # 如果至少有一个关键字匹配，按匹配数量加权
        if matched_count > 0:
            # 平均分 * 匹配率（匹配的关键字越多，分数越高）
            avg_score = total_score / matched_count
            # 匹配率越高，加分越多，但最多加20分
            match_ratio = matched_count / len(keywords)
            match_bonus = match_ratio * 25
            return min(avg_score + match_bonus, 100.0)

        # 没有任何匹配，返回极低分
        return 1.0

    def _calculate_popularity_score(self, article: dict[str, Any]) -> float:
        """
        计算热度分数
        基于内容长度、标题质量等代理指标
        """
        score = 50.0  # 基础分

        # 内容长度（更长的文章通常更重要）
        content = article.get('content') or ''
        if len(content) > 2000:
            score += 20
        elif len(content) > 1000:
            score += 10
        elif len(content) > 500:
            score += 5

        # 标题长度（适中的标题通常更好）
        title = article.get('title') or ''
        title_len = len(title)
        if 20 <= title_len <= 100:
            score += 15
        elif title_len > 10:
            score += 10

        # 是否有作者（有作者通常更可信）
        if article.get('author'):
            score += 10

        # 状态分数
        status = article.get('status')
        if status == ArticleStatus.SYNCED.value:
            score += 5
        elif status == ArticleStatus.PROCESSED.value:
            score += 3

        return min(score, 100.0)

    def _calculate_recency_score(
        self,
        publish_time: datetime | None,
        current_time: datetime,
    ) -> float:
        """
        计算时效性分数
        越新的文章分数越高
        """
        if publish_time is None:
            return 50.0  # 默认中等分数

        # 统一时区处理：如果 publish_time 是 naive，视为 UTC 时间
        # 如果是 aware，转换为 UTC 后去掉时区信息
        if publish_time.tzinfo is None:
            # naive datetime，视为 UTC
            publish_time_naive = publish_time
        else:
            # aware datetime，转换为 UTC 后去掉时区信息
            publish_time_utc = publish_time.astimezone(timezone.utc)
            publish_time_naive = publish_time_utc.replace(tzinfo=None)

        # current_time 应该是 aware datetime (UTC)，也转为 naive 进行计算
        if current_time.tzinfo is not None:
            current_time_naive = current_time.astimezone(timezone.utc).replace(tzinfo=None)
        else:
            current_time_naive = current_time

        age_hours = (current_time_naive - publish_time_naive).total_seconds() / 3600

        # 24小时内：100分
        if age_hours < 24:
            return 100.0
        # 3天内：80分
        elif age_hours < 72:
            return 80.0
        # 7天内：60分
        elif age_hours < 168:
            return 60.0
        # 30天内：40分
        elif age_hours < 720:
            return 40.0
        # 更早：20分
        else:
            return 20.0


class AggregatorConfig:
    """聚合器配置"""

    # 大数据分片阈值
    SHARD_THRESHOLD = 5000

    # 第一阶段筛选数量
    STAGE_ONE_LIMIT = 100

    # 第二阶段 AI 筛选数量
    STAGE_TWO_LIMIT = 20

    # SimHash 相似度阈值
    SIMHASH_THRESHOLD = 0.85


class DataAggregator:
    """
    海量数据聚合 Agent（优化版）
    支持分片处理 + SimHash 聚类
    """

    def __init__(
        self,
        session: AsyncSession,
        scorer: InfluenceScorer | None = None,
        cluster: TextCluster | None = None,
    ) -> None:
        """
        初始化聚合器

        Args:
            session: 数据库会话
            scorer: 影响力评分器
            cluster: 文本聚类器
        """
        self.session = session
        self.article_repo = ArticleRepository(session)

        self.scorer = scorer or InfluenceScorer()
        self.cluster = cluster or TextCluster(
            simhash_bits=64,
            similarity_threshold=AggregatorConfig.SIMHASH_THRESHOLD,
        )

    async def aggregate_core_events(
        self,
        time_range: str = 'week',
        source_ids: list[int] | None = None,
        keywords: list[str] | None = None,
        ai_selector: Any | None = None,
    ) -> list[dict[str, Any]]:
        """
        聚合核心事件
        支持万级数据的分片处理

        Args:
            time_range: 时间范围 ('week' or 'month')
            source_ids: 指定的源 ID 列表
            keywords: 关键词筛选
            ai_selector: AI 选择函数

        Returns:
            核心事件文章列表
        """
        logger.info(f"Starting aggregation for time_range={time_range}")

        # 计算时间范围
        days = 7 if time_range == 'week' else 30
        start_date = datetime.now() - timedelta(days=days)

        # === 第一阶段：获取数据 ===
        logger.info("Stage 1: Data fetching")

        all_articles = await self._fetch_articles_optimized(
            start_date=start_date,
            source_ids=source_ids,
            keywords=keywords,
        )

        total_count = len(all_articles)
        logger.info(f"Fetched {total_count} articles")

        if not all_articles:
            return []

        # === 检查是否需要分片处理 ===
        if total_count > AggregatorConfig.SHARD_THRESHOLD:
            logger.info(f"Large dataset ({total_count} articles), using sharded processing")
            return await self._aggregate_with_sharding(
                all_articles,
                ai_selector,
                start_date,
            )

        # === 常规处理流程 ===
        return await self._aggregate_standard(
            all_articles,
            ai_selector,
        )

    async def _aggregate_standard(
        self,
        articles: list[dict[str, Any]],
        ai_selector: Any | None,
    ) -> list[dict[str, Any]]:
        """
        标准聚合流程（适用于 < 5000 篇文章）
        """
        # 计算影响力分数
        for article in articles:
            article['_score'] = self.scorer.calculate_score(article)

        # SimHash 聚类去重
        logger.info("Stage 2: SimHash clustering")
        clusters = self._cluster_articles_simhash(articles)

        # 每个聚类只保留分数最高的文章
        deduplicated_articles = self._select_representatives(articles, clusters)

        logger.info(f"After deduplication: {len(deduplicated_articles)} unique articles")

        # 按分数排序，取前 N 篇
        deduplicated_articles.sort(key=lambda a: a['_score'], reverse=True)
        stage_one_articles = deduplicated_articles[:AggregatorConfig.STAGE_ONE_LIMIT]

        logger.info(f"Stage 3 selected top {len(stage_one_articles)} articles")

        # === 第二阶段：AI 焦点筛选 ===
        stage_two_articles = await self._ai_selection(
            stage_one_articles,
            ai_selector,
        )

        # 清理临时字段
        for article in stage_two_articles:
            article.pop('_score', None)

        return stage_two_articles

    async def _aggregate_with_sharding(
        self,
        articles: list[dict[str, Any]],
        ai_selector: Any | None,
        start_date: datetime,
    ) -> list[dict[str, Any]]:
        """
        分片聚合流程（适用于 > 5000 篇文章）
        """
        logger.info("Stage 2: Sharded processing")

        # 按来源分片
        shards = self._shard_by_source(articles)
        logger.info(f"Created {len(shards)} source shards")

        # 或按天分片（如果来源数量很少）
        if len(shards) < 3:
            shards = self._shard_by_day(articles, start_date)
            logger.info(f"Created {len(shards)} day shards")

        # 并发处理每个分片
        shard_results = []

        for shard_name, shard_articles in shards.items():
            logger.info(f"Processing shard: {shard_name} ({len(shard_articles)} articles)")

            # 对每个分片进行标准处理
            shard_top = await self._aggregate_standard(shard_articles, None)

            # 每个分片最多保留 10 篇
            shard_results.extend(shard_top[:10])

        logger.info(f"Sharding produced {len(shard_results)} candidates")

        # 对所有分片结果进行最终的 SimHash 去重
        logger.info("Stage 3: Cross-shard deduplication")
        cross_clusters = self._cluster_articles_simhash(shard_results)
        final_articles = self._select_representatives(shard_results, cross_clusters)

        # 按分数排序
        final_articles.sort(key=lambda a: a['_score'], reverse=True)
        final_articles = final_articles[:AggregatorConfig.STAGE_ONE_LIMIT]

        # AI 最终筛选
        final_articles = await self._ai_selection(final_articles, ai_selector)

        # 清理临时字段
        for article in final_articles:
            article.pop('_score', None)

        return final_articles

    def _cluster_articles_simhash(
        self,
        articles: list[dict[str, Any]],
    ) -> dict[int, list[int]]:
        """
        使用 SimHash 对文章进行聚类

        Args:
            articles: 文章列表

        Returns:
            聚类结果：{代表 ID: [相似 ID 列表]}
        """
        # 提取标题和内容用于聚类
        texts = []
        ids = []

        for article in articles:
            # 使用标题 + 前 500 字内容
            title = article.get('title') or ''
            content = (article.get('content') or '')[:500]
            combined = f"{title}. {content}"

            texts.append(combined)
            ids.append(article['id'])

        # 使用 TextCluster 进行聚类
        return self.cluster.cluster_texts(texts, ids)

    def _select_representatives(
        self,
        articles: list[dict[str, Any]],
        clusters: dict[int, list[int]],
    ) -> list[dict[str, Any]]:
        """
        从聚类中选择代表文章

        Args:
            articles: 原始文章列表
            clusters: 聚类结果

        Returns:
            代表文章列表
        """
        # 创建 ID 到文章的映射
        article_map = {a['id']: a for a in articles}

        representatives = []

        for rep_id, similar_ids in clusters.items():
            # 添加代表文章
            if rep_id in article_map:
                representatives.append(article_map[rep_id])

            # 相似文章不需要添加，已经去重

        return representatives

    def _shard_by_source(
        self,
        articles: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """按来源分片"""
        shards = defaultdict(list)
        for article in articles:
            source_id = article.get('source_id', 0)
            shards[f"source_{source_id}"].append(article)
        return dict(shards)

    def _shard_by_day(
        self,
        articles: list[dict[str, Any]],
        start_date: datetime,
    ) -> dict[str, list[dict[str, Any]]]:
        """按日期分片"""
        shards = defaultdict(list)
        for article in articles:
            created_at = article.get('created_at') or article.get('publish_time')
            if created_at:
                day_key = created_at.strftime('%Y-%m-%d')
                shards[day_key].append(article)
            else:
                shards['unknown'].append(article)
        return dict(shards)

    async def _ai_selection(
        self,
        articles: list[dict[str, Any]],
        ai_selector: Any | None,
    ) -> list[dict[str, Any]]:
        """
        AI 筛选阶段

        Args:
            articles: 文章列表
            ai_selector: AI 选择函数

        Returns:
            筛选后的文章列表
        """
        if ai_selector is None:
            # 没有 AI 选择器，直接按分数选择
            return articles[:AggregatorConfig.STAGE_TWO_LIMIT]

        logger.info("Stage 4: AI-based selection")

        # 准备发给 AI 的摘要
        summaries = self._prepare_summaries(articles)

        try:
            # 调用 AI 选择核心事件
            selected_ids = await ai_selector(
                summaries,
                limit=AggregatorConfig.STAGE_TWO_LIMIT,
                prompt=self._get_ai_selection_prompt(),
            )

            # 根据返回的 ID 筛选文章
            id_set = set(selected_ids)
            selected_articles = [
                a for a in articles
                if a['id'] in id_set
            ]

            logger.info(f"AI selected {len(selected_articles)} core events")
            return selected_articles

        except Exception as e:
            logger.error(f"AI selection failed: {e}")
            # 回退到按分数选择
            return articles[:AggregatorConfig.STAGE_TWO_LIMIT]

    def _prepare_summaries(
        self,
        articles: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        准备发给 AI 的摘要
        """
        summaries = []

        for article in articles:
            # 生成简短摘要（前 200 字）
            content = article.get('content') or ''
            summary = content[:200] + '...' if len(content) > 200 else content

            summaries.append({
                'id': article['id'],
                'title': article.get('title', ''),
                'summary': summary,
                'publish_time': article.get('publish_time'),
                'source_id': article.get('source_id'),
                'score': article.get('_score', 0),
            })

        return summaries

    @staticmethod
    def _get_ai_selection_prompt() -> str:
        """
        获取 AI 选择 Prompt

        Returns:
            Prompt 文本
        """
        return """你是一位资深新闻编辑。你的任务是从一系列新闻中筛选出最具社会影响力的核心事件。

筛选标准：
1. **社会影响力**：优先选择对社会、政治、经济产生重大影响的事件
2. **新闻价值**：考虑事件的时效性、重要性、接近性
3. **独特性**：避免选择重复或过于相似的事件
4. **深度**：优先选择有深度分析和详细报道的文章

请从以下 {total} 篇文章中，选择出 {limit} 个最具影响力的核心事件。

返回格式：
仅返回选中的文章 ID 列表，用逗号分隔，如：1, 5, 12, 23, 45, ...

{summaries}

请基于以上信息，返回选中的文章 ID："""

    async def _fetch_articles_optimized(
        self,
        start_date: datetime,
        source_ids: list[int] | None = None,
        keywords: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        优化的文章获取
        使用索引优化查询性能
        基于文章发布时间 (publish_time) 筛选，如果没有发布时间则使用抓取时间
        """
        # 构建查询条件 - 使用 publish_time 作为主要筛选条件
        # 如果 publish_time 为 NULL，则使用 crawled_at 作为备选
        params: dict[str, Any] = {'start_date': start_date}
        where_clauses = ["(publish_time >= :start_date OR (publish_time IS NULL AND crawled_at >= :start_date))"]

        if source_ids:
            placeholders = ', '.join(f':sid_{i}' for i in range(len(source_ids)))
            where_clauses.append(f"source_id IN ({placeholders})")
            for i, sid in enumerate(source_ids):
                params[f'sid_{i}'] = sid

        where_clause = ' AND '.join(where_clauses)

        # 使用优化的查询，利用复合索引
        sql = f"""
            SELECT
                id, url_hash, url, title, content, publish_time,
                author, source_id, status, fetch_status,
                crawled_at, processed_at, created_at, updated_at
            FROM articles
            WHERE {where_clause}
            ORDER BY source_id, status, COALESCE(publish_time, crawled_at) DESC
        """

        results = await self.article_repo.fetch_all(sql, params)
        return [dict(r) for r in results]

    async def get_statistics(
        self,
        days: int = 30,
    ) -> dict[str, Any]:
        """
        获取数据统计信息
        """
        start_date = datetime.now() - timedelta(days=days)

        articles = await self._fetch_articles_optimized(start_date=start_date)

        stats = {
            'total_articles': len(articles),
            'by_source': {},
            'by_status': {},
            'average_score': 0.0,
        }

        if not articles:
            return stats

        # 计算分数
        total_score = 0.0
        for article in articles:
            score = self.scorer.calculate_score(article)
            total_score += score

            # 按源统计
            source_id = article.get('source_id', 0)
            stats['by_source'][source_id] = stats['by_source'].get(source_id, 0) + 1

            # 按状态统计
            status = article.get('status', 'unknown')
            stats['by_status'][status] = stats['by_status'].get(status, 0) + 1

        stats['average_score'] = total_score / len(articles) if articles else 0.0

        return stats
