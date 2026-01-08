#!/usr/bin/env python3
"""
批量重新爬取文章脚本
用于修复图片提取问题，支持增量重新爬取
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from src.core.database import get_async_session
from src.repository.article_repository import ArticleRepository
from src.repository.source_repository import SourceRepository
from src.services.scraper import UniversalScraper
from src.core.models import CrawlSource


async def refetch_articles(
    limit: int | None = None,
    source_id: int | None = None,
    days: int | None = None,
    force_all: bool = False,
    batch_size: int = 10,
    delay: float = 1.0,
) -> dict:
    """
    批量重新爬取文章

    Args:
        limit: 最多重新爬取的文章数量
        source_id: 只重新爬取指定源的文章
        days: 只重新爬取最近N天的文章
        force_all: 是否重新爬取所有文章（包括已成功的）
        batch_size: 每批处理的数量
        delay: 每批之间的延迟（秒）

    Returns:
        统计信息
    """
    stats = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }

    async with get_async_session() as db:
        article_repo = ArticleRepository(db)
        source_repo = SourceRepository(db)

        # 获取所有启用的爬虫源
        sources = await source_repo.get_enabled_sources()

        if not sources:
            print("没有找到启用的爬虫源")
            return stats

        print(f"找到 {len(sources)} 个启用的爬虫源")

        # 创建爬虫实例
        async with UniversalScraper() as scraper:
            for source in sources:
                if source_id and source.id != source_id:
                    continue

                print(f"\n处理源: {source.site_name} (ID: {source.id})")

                # 构建查询条件
                conditions = {"source_id": source.id}

                if not force_all:
                    # 只重新爬取失败或需要更新的文章
                    conditions["fetch_status"] = ["failed", "retry"]

                if days:
                    # 只处理最近N天的文章
                    since = datetime.now() - timedelta(days=days)
                    conditions["created_after"] = since

                # 获取需要重新爬取的文章列表
                articles = await article_repo.list(**conditions)

                if limit and len(articles) > limit:
                    articles = articles[:limit]

                if not articles:
                    print(f"  没有需要重新爬取的文章")
                    continue

                stats["total"] += len(articles)
                print(f"  找到 {len(articles)} 篇文章需要重新爬取")

                # 批量处理
                for i in range(0, len(articles), batch_size):
                    batch = articles[i : i + batch_size]
                    batch_num = i // batch_size + 1
                    total_batches = (len(articles) + batch_size - 1) // batch_size

                    print(f"\n  批次 {batch_num}/{total_batches} ({len(batch)} 篇文章)")

                    for article in batch:
                        try:
                            print(f"    爬取: {article['title'][:50]}...")

                            # 重新爬取
                            result = await scraper.scrape_article(article["url"], source)

                            if result:
                                # 更新文章
                                update_data = {
                                    "title": result.title,
                                    "content": result.content,
                                    "publish_time": result.publish_time,
                                    "author": result.author,
                                    "extra_data": result.extra_data,
                                    "fetch_status": "success",
                                    "status": "raw",
                                    "error_message": None,
                                    "retry_count": 0,
                                }

                                await article_repo.update(article["id"], update_data)
                                stats["success"] += 1
                                print(f"      ✓ 成功 (图片: {len(result.extra_data.get('images', [])) if result.extra_data else 0} 张)")

                            else:
                                stats["failed"] += 1
                                error_msg = f"爬取失败: {article['url']}"
                                stats["errors"].append(error_msg)
                                print(f"      ✗ 失败")

                        except Exception as e:
                            stats["failed"] += 1
                            error_msg = f"{article['url']}: {str(e)}"
                            stats["errors"].append(error_msg)
                            print(f"      ✗ 错误: {e}")

                    # 批次间延迟
                    if i + batch_size < len(articles):
                        print(f"    等待 {delay} 秒...")
                        await asyncio.sleep(delay)

    return stats


async def refetch_by_ids(article_ids: list[int], batch_size: int = 10, delay: float = 1.0) -> dict:
    """
    根据文章ID列表重新爬取

    Args:
        article_ids: 文章ID列表
        batch_size: 每批处理的数量
        delay: 每批之间的延迟（秒）

    Returns:
        统计信息
    """
    stats = {
        "total": len(article_ids),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "errors": [],
    }

    async with get_async_session() as db:
        article_repo = ArticleRepository(db)
        source_repo = SourceRepository(db)

        # 获取文章
        articles = []
        for aid in article_ids:
            article = await article_repo.get_by_id(aid)
            if article:
                articles.append(article)

        if not articles:
            print("没有找到指定的文章")
            return stats

        print(f"找到 {len(articles)} 篇文章")

        # 获取对应的爬虫源
        sources = await source_repo.get_enabled_sources()
        source_map = {s.id: s for s in sources}

        async with UniversalScraper() as scraper:
            for i, article in enumerate(articles, 1):
                source = source_map.get(article["source_id"])

                if not source:
                    print(f"[{i}/{len(articles)}] 跳过: 未找到源 (ID: {article['source_id']})")
                    stats["skipped"] += 1
                    continue

                try:
                    print(f"[{i}/{len(articles)}] 爬取: {article['title'][:50]}...")

                    result = await scraper.scrape_article(article["url"], source)

                    if result:
                        update_data = {
                            "title": result.title,
                            "content": result.content,
                            "publish_time": result.publish_time,
                            "author": result.author,
                            "extra_data": result.extra_data,
                            "fetch_status": "success",
                            "status": "raw",
                            "error_message": None,
                            "retry_count": 0,
                        }

                        await article_repo.update(article["id"], update_data)
                        stats["success"] += 1
                        img_count = len(result.extra_data.get('images', [])) if result.extra_data else 0
                        print(f"  ✓ 成功 (图片: {img_count} 张)")

                    else:
                        stats["failed"] += 1
                        print(f"  ✗ 失败")

                except Exception as e:
                    stats["failed"] += 1
                    stats["errors"].append(f"{article['url']}: {str(e)}")
                    print(f"  ✗ 错误: {e}")

                # 延迟
                if i < len(articles):
                    await asyncio.sleep(delay)

    return stats


async def show_statistics() -> None:
    """显示文章统计信息"""
    async with get_async_session() as db:
        article_repo = ArticleRepository(db)

        # 获取大量文章来统计
        total_articles = await article_repo.get_latest_articles(limit=10000)
        total = len(total_articles)

        # 按状态统计
        success = sum(1 for a in total_articles if a.get("fetch_status") == "success")
        failed = sum(1 for a in total_articles if a.get("fetch_status") == "failed")
        pending = sum(1 for a in total_articles if a.get("fetch_status") == "pending")

        # 有图片的文章数
        with_images = sum(1 for a in total_articles if a.get("extra_data") and a.get("extra_data", {}).get("images"))

        print("\n文章统计:")
        print(f"  总数:     {total}")
        print(f"  成功:     {success}")
        print(f"  失败:     {failed}")
        print(f"  待处理:   {pending}")
        if total > 0:
            print(f"  有图片:   {with_images} ({with_images/total*100:.1f}%)")
        else:
            print(f"  有图片:   0")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="批量重新爬取文章",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 重新爬取最近7天失败的文章
  python scripts/refetch_articles.py --days 7

  # 重新爬取指定源的所有失败文章
  python scripts/refetch_articles.py --source-id 1

  # 重新爬取最多100篇文章
  python scripts/refetch_articles.py --limit 100

  # 强制重新爬取所有文章
  python scripts/refetch_articles.py --force-all --limit 50

  # 根据文章ID重新爬取
  python scripts/refetch_articles.py --ids 123 456 789

  # 显示统计信息
  python scripts/refetch_articles.py --stats
        """,
    )

    parser.add_argument("--limit", "-l", type=int, help="最多重新爬取的文章数量")
    parser.add_argument("--source-id", "-s", type=int, help="只重新爬取指定源的文章")
    parser.add_argument("--days", "-d", type=int, help="只重新爬取最近N天的文章")
    parser.add_argument("--force-all", "-f", action="store_true", help="强制重新爬取所有文章（包括已成功的）")
    parser.add_argument("--batch-size", "-b", type=int, default=10, help="每批处理的数量（默认: 10）")
    parser.add_argument("--delay", type=float, default=1.0, help="每批之间的延迟秒数（默认: 1.0）")
    parser.add_argument("--ids", nargs="+", type=int, help="根据文章ID重新爬取")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")

    args = parser.parse_args()

    if args.stats:
        asyncio.run(show_statistics())
    elif args.ids:
        stats = asyncio.run(refetch_by_ids(args.ids, args.batch_size, args.delay))
    else:
        stats = asyncio.run(refetch_articles(
            limit=args.limit,
            source_id=args.source_id,
            days=args.days,
            force_all=args.force_all,
            batch_size=args.batch_size,
            delay=args.delay,
        ))

    # 打印结果
    if not args.stats:
        print("\n" + "=" * 50)
        print("重新爬取完成!")
        print(f"  总计:   {stats['total']}")
        print(f"  成功:   {stats['success']}")
        print(f"  失败:   {stats['failed']}")
        print(f"  跳过:   {stats['skipped']}")

        if stats["errors"]:
            print(f"\n错误列表 (最多显示10条):")
            for error in stats["errors"][:10]:
                print(f"  - {error}")
