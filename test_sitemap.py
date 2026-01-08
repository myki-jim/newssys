#!/usr/bin/env python3
"""
Sitemap 功能测试脚本

测试以下功能：
1. 创建源
2. 从 robots.txt 发现 Sitemap
3. 解析 Sitemap 并提取文章链接
4. 导入到待爬表
"""

import asyncio
import sys
sys.path.insert(0, '/Users/jimmyki/Documents/Code/news')

from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_async_session
from src.repository.source_repository import SourceRepository
from src.repository.sitemap_repository import SitemapRepository
from src.repository.pending_article_repository import PendingArticleRepository
from src.services.sitemap_service import SitemapService
from src.core.models import SourceCreate, ParserConfig


async def test_sitemap_discovery():
    """测试 Sitemap 发现功能"""

    async with get_async_session() as db:
        print("=" * 60)
        print("Sitemap 功能测试")
        print("=" * 60)

        # 1. 创建测试源（BBC）
        print("\n[1] 创建测试源...")
        source_repo = SourceRepository(db)

        # 检查是否已存在
        existing = await source_repo.fetch_by_base_url("https://www.bbc.com")
        if existing:
            source_id = existing["id"]
            print(f"   源已存在: ID={source_id}")
        else:
            source = SourceCreate(
                site_name="BBC News",
                base_url="https://www.bbc.com",
                parser_config=ParserConfig(
                    title_selector="h1",
                    content_selector="article, main",
                ),
                enabled=False,  # 默认禁用
            )
            result = await source_repo.create(source)
            source_id = result["id"]
            print(f"   源已创建: ID={source_id}")

        # 2. 从 robots.txt 发现 Sitemap
        print(f"\n[2] 从 robots.txt 发现 Sitemap (源 ID={source_id})...")
        service = SitemapService(db)

        try:
            sitemaps = await service.fetch_robots_sitemaps(source_id)
            print(f"   发现 {len(sitemaps)} 个 Sitemap:")
            for sitemap in sitemaps:
                print(f"     - {sitemap.url}")

            if not sitemaps:
                print("   未发现 Sitemap，尝试手动添加...")
                # 手动添加 BBC 的 sitemap
                result = await service.add_custom_sitemap(
                    source_id=source_id,
                    sitemap_url="https://www.bbc.com/sitemap.xml"
                )
                print(f"   手动添加 Sitemap: {result}")

                # 重新获取
                sitemaps = await service.fetch_robots_sitemaps(source_id)

        finally:
            await service.close()

        # 3. 查看数据库中的 Sitemap
        print(f"\n[3] 查看数据库中的 Sitemap...")
        sitemap_repo = SitemapRepository(db)
        db_sitemaps = await sitemap_repo.get_by_source(source_id)
        print(f"   数据库中有 {len(db_sitemaps)} 个 Sitemap:")
        for sm in db_sitemaps:
            print(f"     - ID={sm['id']}, URL={sm['url']}, 状态={sm['fetch_status']}")

        # 4. 解析第一个 Sitemap
        if db_sitemaps:
            first_sitemap_id = db_sitemaps[0]['id']
            print(f"\n[4] 解析 Sitemap {first_sitemap_id}...")

            service = SitemapService(db)
            try:
                result = await service.fetch_and_parse_sitemap(first_sitemap_id, recursive=False)
                print(f"   叶子 Sitemap: {result.get('leaf_sitemaps', [])}")
                print(f"   发现文章数: {len(result.get('articles', []))}")

                # 显示前几个文章
                articles = result.get('articles', [])[:3]
                for i, art in enumerate(articles, 1):
                    print(f"     [{i}] {art.url[:80]}...")
                    if art.title:
                        print(f"         标题: {art.title}")
                    if art.publish_time:
                        print(f"         时间: {art.publish_time}")

            finally:
                await service.close()

        # 5. 导入到待爬表
        print(f"\n[5] 导入文章到待爬表...")
        service = SitemapService(db)
        try:
            sync_result = await service.sync_source_sitemaps(source_id)
            print(f"   Sitemap 数量: {sync_result.get('sitemaps_found', 0)}")
            print(f"   新增文章: {sync_result.get('articles_imported', 0)}")
            print(f"   已存在文章: {sync_result.get('articles_existing', 0)}")
        finally:
            await service.close()

        # 6. 查看待爬表统计
        print(f"\n[6] 查看待爬表统计...")
        pending_repo = PendingArticleRepository(db)
        total = await pending_repo.count_by_source(source_id)
        pending = await pending_repo.count_by_source(source_id, status="pending")
        print(f"   总数: {total}")
        print(f"   待爬: {pending}")

        # 获取前几个待爬文章
        pending_articles = await pending_repo.get_by_source(source_id, limit=3)
        print(f"   前 3 个待爬文章:")
        for art in pending_articles[:3]:
            print(f"     - {art['url'][:80]}...")

        print("\n" + "=" * 60)
        print("测试完成！")
        print("=" * 60)

        # 显示 API 端点
        print("\n可用的 API 端点:")
        print(f"  GET    /api/v1/sources/{source_id}/sitemap")
        print(f"  POST   /api/v1/sources/{source_id}/sitemap/discover")
        print(f"  POST   /api/v1/sources/{source_id}/sitemap/sync")
        print(f"  GET    /api/v1/sitemaps/pending?source_id={source_id}")
        print(f"  GET    /api/v1/sitemaps/pending/stats?source_id={source_id}")


if __name__ == "__main__":
    asyncio.run(test_sitemap_discovery())
