"""
仪表盘 API
/api/v1/dashboard

提供系统统计数据和监控信息
"""

import collections
import logging
from datetime import datetime, timedelta
from typing import Any

import jieba.analyse
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import APIResponse, DashboardStats
from src.repository.article_repository import ArticleRepository
from src.repository.source_repository import SourceRepository


logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# 依赖注入
# ============================================================================

async def get_db() -> AsyncSession:  # type: ignore
    """获取数据库会话"""
    from src.core.database import get_async_session
    async with get_async_session() as session:
        yield session


# ============================================================================
# 统计数据
# ============================================================================

@router.get("/stats", response_model=APIResponse[DashboardStats])
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    获取仪表盘统计数据

    包括:
    - 源统计
    - 文章统计
    - 报告统计
    - 存储使用情况
    """
    article_repo = ArticleRepository(db)
    source_repo = SourceRepository(db)

    # 今日开始时间
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # 源统计
    all_sources = await source_repo.fetch_many(filters={}, limit=10000)
    total_sources = len(all_sources)
    active_sources = sum(1 for s in all_sources if s["enabled"])

    # 文章统计（过滤掉低质量文章）
    total_articles_sql = "SELECT COUNT(*) as count FROM articles WHERE status != 'low_quality'"
    total_articles_result = await article_repo.fetch_one(total_articles_sql, {})
    total_articles = total_articles_result["count"] if total_articles_result else 0

    today_articles_sql = "SELECT COUNT(*) as count FROM articles WHERE created_at >= :today AND status != 'low_quality'"
    today_articles_result = await article_repo.fetch_one(today_articles_sql, {"today": today_start})
    today_articles = today_articles_result["count"] if today_articles_result else 0

    failed_articles_sql = "SELECT COUNT(*) as count FROM articles WHERE (status = 'failed' OR fetch_status = 'failed') AND status != 'low_quality'"
    failed_articles_result = await article_repo.fetch_one(failed_articles_sql, {})
    failed_articles = failed_articles_result["count"] if failed_articles_result else 0

    # 报告统计
    reports_sql = "SELECT COUNT(*) as count FROM report_metadata"
    reports_result = await article_repo.fetch_one(reports_sql, {})
    total_reports = reports_result["count"] if reports_result else 0

    # 存储使用（估算）
    storage_sql = """
        SELECT
            COALESCE(SUM(LENGTH(COALESCE(title, ''))), 0) +
            COALESCE(SUM(LENGTH(COALESCE(content, ''))), 0) +
            COALESCE(SUM(LENGTH(COALESCE(error_message, ''))), 0) as total_bytes
        FROM articles
    """
    storage_result = await article_repo.fetch_one(storage_sql, {})
    total_bytes = storage_result["total_bytes"] if storage_result and storage_result["total_bytes"] else 0
    storage_used_mb = round(total_bytes / (1024 * 1024), 2)

    stats = DashboardStats(
        total_sources=total_sources,
        active_sources=active_sources,
        total_articles=total_articles,
        today_articles=today_articles,
        failed_articles=failed_articles,
        total_reports=total_reports,
        storage_used_mb=storage_used_mb,
    )

    return APIResponse(success=True, data=stats)


@router.get("/timeline")
async def get_timeline_stats(
    days: int = Query(default=30, ge=1, le=365, description="统计天数"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取时间线统计数据

    用于绘制趋势图:
    - 每日新增文章数
    - 每日成功/失败数
    """
    start_date = datetime.now() - timedelta(days=days)

    sql = """
        SELECT
            DATE(created_at) as date,
            COUNT(*) as total,
            SUM(CASE WHEN status = 'processed' THEN 1 ELSE 0 END) as processed,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
        FROM articles
        WHERE created_at >= :start_date
        GROUP BY DATE(created_at)
        ORDER BY date ASC
    """

    article_repo = ArticleRepository(db)
    results = await article_repo.fetch_all(sql, {"start_date": start_date})

    timeline = [
        {
            "date": str(r["date"]),
            "total": r["total"],
            "processed": r["processed"] or 0,
            "failed": r["failed"] or 0,
        }
        for r in results
    ]

    return APIResponse(success=True, data=timeline)


@router.get("/top-sources")
async def get_top_sources(
    limit: int = Query(default=10, ge=1, le=50, description="返回数量"),
    days: int = Query(default=7, ge=1, le=90, description="统计天数"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取最活跃的源

    基于:
    - 文章数量
    - 成功率
    """
    start_date = datetime.now() - timedelta(days=days)

    sql = """
        SELECT
            s.id as source_id,
            s.site_name,
            COUNT(a.id) as total_articles,
            SUM(CASE WHEN a.status = 'processed' THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN a.status = 'failed' THEN 1 ELSE 0 END) as failure_count,
            MAX(a.created_at) as last_article_at
        FROM crawl_sources s
        LEFT JOIN articles a ON s.id = a.source_id AND a.created_at >= :start_date
        WHERE s.enabled = 1
        GROUP BY s.id, s.site_name
        HAVING total_articles > 0
        ORDER BY total_articles DESC
        LIMIT :limit
    """

    article_repo = ArticleRepository(db)
    results = await article_repo.fetch_all(sql, {"start_date": start_date, "limit": limit})

    top_sources = []
    for r in results:
        total = r["total_articles"] or 0
        success = r["success_count"] or 0
        failure = r["failure_count"] or 0

        top_sources.append({
            "source_id": r["source_id"],
            "site_name": r["site_name"],
            "total_articles": total,
            "success_count": success,
            "failure_count": failure,
            "success_rate": round(success / total * 100, 2) if total > 0 else 0,
            "last_article_at": str(r["last_article_at"]) if r["last_article_at"] else None,
        })

    return APIResponse(success=True, data=top_sources)


@router.get("/recent-activity")
async def get_recent_activity(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    获取最近的活动记录

    包括:
    - 新增文章
    - 状态变更
    - 报告生成
    """
    article_repo = ArticleRepository(db)

    # 获取最近的文章
    articles_sql = """
        SELECT
            id, title, source_id, status, created_at
        FROM articles
        ORDER BY created_at DESC
        LIMIT :limit
    """

    articles = await article_repo.fetch_all(articles_sql, {"limit": limit})

    activities = [
        {
            "type": "article",
            "id": a["id"],
            "title": a["title"][:100],
            "source_id": a["source_id"],
            "status": a["status"],
            "created_at": str(a["created_at"]),
        }
        for a in articles
    ]

    # TODO: 添加报告活动

    return APIResponse(success=True, data=activities)


@router.get("/health")
async def get_system_health(
    db: AsyncSession = Depends(get_db),
):
    """
    获取系统健康状态

    检查:
    - 数据库连接
    - 待处理任务数量
    - 错误率
    """
    article_repo = ArticleRepository(db)
    source_repo = SourceRepository(db)

    health_status = "healthy"
    issues = []

    # 检查待处理文章（包括 articles 表和 pending_articles 表，过滤掉低质量）
    pending_articles_sql = "SELECT COUNT(*) as count FROM articles WHERE fetch_status = 'pending' AND status != 'low_quality'"
    pending_articles_result = await article_repo.fetch_one(pending_articles_sql, {})
    pending_articles_count = pending_articles_result["count"] if pending_articles_result else 0

    pending_sitemap_sql = "SELECT COUNT(*) as count FROM pending_articles WHERE status = 'pending'"
    pending_sitemap_result = await article_repo.fetch_one(pending_sitemap_sql, {})
    pending_sitemap_count = pending_sitemap_result["count"] if pending_sitemap_result else 0

    pending_count = pending_articles_count + pending_sitemap_count

    # 检查需要重试的文章（过滤掉低质量）
    retry_sql = "SELECT COUNT(*) as count FROM articles WHERE fetch_status = 'retry' AND status != 'low_quality'"
    retry_result = await article_repo.fetch_one(retry_sql, {})
    retry_count = retry_result["count"] if retry_result else 0

    # 检查失败率（过滤掉低质量）
    total_sql = "SELECT COUNT(*) as count FROM articles WHERE created_at >= :since AND status != 'low_quality'"
    total_result = await article_repo.fetch_one(total_sql, {"since": datetime.now() - timedelta(hours=24)})
    total_count = total_result["count"] if total_result else 0

    failed_sql = "SELECT COUNT(*) as count FROM articles WHERE (status = 'failed' OR fetch_status = 'failed') AND created_at >= :since AND status != 'low_quality'"
    failed_result = await article_repo.fetch_one(failed_sql, {"since": datetime.now() - timedelta(hours=24)})
    failed_count = failed_result["count"] if failed_result else 0

    failure_rate = round(failed_count / total_count * 100, 2) if total_count > 0 else 0

    # 判断健康状态
    if failure_rate > 50:
        health_status = "critical"
        issues.append(f"High failure rate: {failure_rate}%")
    elif failure_rate > 20:
        health_status = "warning"
        issues.append(f"Elevated failure rate: {failure_rate}%")

    if retry_count > 1000:
        health_status = "warning"
        issues.append(f"High retry queue: {retry_count} articles")

    return APIResponse(
        success=True,
        data={
            "status": health_status,
            "issues": issues,
            "metrics": {
                "pending_articles": pending_count,
                "retry_queue": retry_count,
                "failure_rate_24h": failure_rate,
            },
        },
    )


@router.get("/stats/trends")
async def get_stats_trends(
    db: AsyncSession = Depends(get_db),
):
    """
    获取统计数据趋势

    返回:
    - hourly_trends: 今天每小时的文章数量
    - pending_status_distribution: 待爬文章状态分布
    - top_titles: 出现频次最高的标题
    - today_stats: 今日统计
    """
    article_repo = ArticleRepository(db)

    # 今天每小时的文章数量趋势（过滤掉低质量文章）
    hourly_trends_sql = """
        SELECT
            strftime('%H', created_at) as hour,
            COUNT(*) as count
        FROM articles
        WHERE DATE(created_at) = DATE('now') AND status != 'low_quality'
        GROUP BY hour
        ORDER BY hour ASC
    """
    hourly_result = await article_repo.fetch_all(hourly_trends_sql, {})

    hourly_trends = [
        {"hour": f"{r['hour']}:00", "count": r["count"]}
        for r in hourly_result
    ]

    # 待爬文章状态分布（从 pending_articles 表）
    pending_status_sql = """
        SELECT
            status,
            COUNT(*) as count
        FROM pending_articles
        GROUP BY status
    """
    pending_status_result = await article_repo.fetch_all(pending_status_sql, {})

    pending_status_distribution = [
        {"name": r["status"] or "null", "value": r["count"]}
        for r in pending_status_result
    ]

    # 出现频次最高的标题（可能是热点新闻，过滤掉低质量文章）
    top_titles_sql = """
        SELECT
            title,
            COUNT(*) as count
        FROM articles
        WHERE title IS NOT NULL AND title != ''
            AND created_at >= DATE('now', '-7 days')
            AND status != 'low_quality'
        GROUP BY title
        HAVING count > 1
        ORDER BY count DESC
        LIMIT 10
    """
    top_titles_result = await article_repo.fetch_all(top_titles_sql, {})

    top_titles = [
        {"title": r["title"][:50], "count": r["count"]}
        for r in top_titles_result
    ]

    # 今日统计数据（修复统计逻辑，过滤掉低质量文章）
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # 今日新增文章总数（过滤掉低质量）
    today_total_sql = """
        SELECT COUNT(*) as count
        FROM articles
        WHERE created_at >= :today AND status != 'low_quality'
    """
    today_total_result = await article_repo.fetch_one(today_total_sql, {"today": today_start})

    # 今日已处理（raw 和 processed 状态都算已处理，过滤掉低质量）
    today_processed_sql = """
        SELECT COUNT(*) as count
        FROM articles
        WHERE created_at >= :today AND status IN ('raw', 'processed')
    """
    today_processed_result = await article_repo.fetch_one(today_processed_sql, {"today": today_start})

    # 今日失败（status = 'failed'）
    today_failed_sql = """
        SELECT COUNT(*) as count
        FROM articles
        WHERE created_at >= :today AND status = 'failed'
    """
    today_failed_result = await article_repo.fetch_one(today_failed_sql, {"today": today_start})

    today_stats = {
        "total": today_total_result["count"] if today_total_result else 0,
        "processed": today_processed_result["count"] if today_processed_result else 0,
        "failed": today_failed_result["count"] if today_failed_result else 0,
    }

    return APIResponse(
        success=True,
        data={
            "hourly_trends": hourly_trends,
            "pending_status_distribution": pending_status_distribution,
            "top_titles": top_titles,
            "today_stats": today_stats,
        },
    )


@router.get("/keywords/cloud")
async def get_keyword_cloud(
    period: str = Query(default="today", description="时间周期: today, week, month, 或 custom"),
    language: str = Query(default="zh", description="语言: zh 或 kk"),
    from_date: str | None = Query(default=None, description="自定义起始日期 (YYYY-MM-DD)"),
    to_date: str | None = Query(default=None, description="自定义结束日期 (YYYY-MM-DD)"),
    limit: int = Query(default=50, ge=10, le=200, description="返回关键词数量"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取关键词词云数据

    从指定时间范围的文章中提取关键词，用于生成词云

    参数:
    - period: today (今天), week (本周), month (本月), 或 custom (自定义日期)
    - language: zh (中文) 或 kk (哈萨克语)
    - from_date: 自定义起始日期 (YYYY-MM-DD)，当 period=custom 时使用
    - to_date: 自定义结束日期 (YYYY-MM-DD)，当 period=custom 时使用
    - limit: 返回的关键词数量

    返回:
    - keywords: 关键词列表，包含关键词和权重
    - from_date: 起始日期
    - to_date: 结束日期
    - total_articles: 文章总数
    """
    article_repo = ArticleRepository(db)

    # 计算时间范围
    now = datetime.now()
    if period == "custom" and from_date:
        # 自定义日期范围
        from_date_dt = datetime.fromisoformat(from_date)
        to_date_dt = datetime.fromisoformat(to_date) if to_date else now
        from_date_calc = from_date_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        to_date_calc = to_date_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == "today":
        # 今天
        from_date_calc = now.replace(hour=0, minute=0, second=0, microsecond=0)
        to_date_calc = now
    elif period == "week":
        # 本周（从周一到现在）
        days_since_monday = now.weekday()
        from_date_calc = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        to_date_calc = now
    else:  # month
        # 本月（从1号到现在）
        from_date_calc = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        to_date_calc = now

    # 使用计算后的日期范围
    from_date_final = from_date_calc if period != "custom" or not from_date else from_date_calc
    to_date_final = to_date_calc

    # 获取时间范围内的文章（支持 raw 和 processed 状态，使用发布时间而不是爬取时间）
    sql = """
        SELECT title, content
        FROM articles
        WHERE COALESCE(publish_time, created_at) >= :from_date
          AND COALESCE(publish_time, created_at) <= :to_date
          AND (status = 'raw' OR status = 'processed')
          AND title IS NOT NULL
          AND title != ''
        LIMIT 5000
    """

    articles = await article_repo.fetch_all(sql, {"from_date": from_date_final, "to_date": to_date_final})

    # 合并所有文章的标题和内容
    all_text = []
    for article in articles:
        if article.get("title"):
            all_text.append(article["title"])
        if article.get("content"):
            # 只取前500字，避免内容过长
            all_text.append(article["content"][:500])

    combined_text = "\n".join(all_text)

    # 根据语言使用不同的分词方式
    if language == "kk":
        # 哈萨克语：按空格分词，统计词频
        import re
        words = re.findall(r'\w+', combined_text)

        # 哈萨克语停用词（基础版本）
        kk_stopwords = {
            "және", "де", "мен", "бұл", "үшін", "болып", "еді", "сол",
            "сияқты", "секілді", "дейін", "дейінгі", "арқылы",
        }

        # 统计词频
        word_freq = {}
        for word in words:
            if len(word) > 2 and word.lower() not in kk_stopwords:
                word_freq[word] = word_freq.get(word, 0) + 1

        # 转换为带权重的关键词列表
        keywords_with_weights = [(word, freq) for word, freq in sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:limit]]
    else:
        # 中文：使用 jieba 分词
        keywords_with_weights = jieba.analyse.extract_tags(
            combined_text,
            topK=limit,
            withWeight=True,
            allowPOS=("n", "nr", "ns", "nt", "nz", "v", "vn"),  # 名词、动词等
        )

    # 停用词过滤（仅中文）
    stopwords = {
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
        "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
        "自己", "这", "年", "月", "日", "时", "分", "秒", "周",
        "可以", "但是", "因为", "所以", "如果", "虽然", "让", "给", "为",
        "表示", "指出", "认为", "称", "据", "报道", "消息", "透露", "相关", "有关",
        "目前", "现在", "正在", "已经", "进行", "工作",
    }

    # 过滤停用词和过短的词
    if language == "kk":
        # 哈萨克语不过滤中文停用词
        filtered_keywords = [
            {"keyword": word, "weight": round(weight * 100 / max(k[1] for k in keywords_with_weights) if keywords_with_weights else 1, 2)}
            for word, weight in keywords_with_weights
            if len(word) > 2
        ]
    else:
        # 中文过滤停用词
        filtered_keywords = [
            {"keyword": word, "weight": round(weight * 100, 2)}
            for word, weight in keywords_with_weights
            if word not in stopwords and len(word) > 1
        ]

    # 归一化权重到 1-100
    if filtered_keywords:
        max_weight = max(k["weight"] for k in filtered_keywords)
        if max_weight > 0:
            for kw in filtered_keywords:
                kw["weight"] = round(kw["weight"] / max_weight * 100, 2)

    return APIResponse(
        success=True,
        data={
            "period": period,
            "language": language,
            "keywords": filtered_keywords[:limit],
            "from_date": from_date_final.isoformat(),
            "to_date": to_date_final.isoformat(),
            "total_articles": len(articles),
        },
    )

