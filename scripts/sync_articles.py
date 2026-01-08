#!/usr/bin/env python3
"""
批量同步文章脚本
重新爬取所有没有内容的文章
"""

import asyncio
import sys
import random
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import aiohttp
import aiofiles
from src.core.database import get_async_session
from src.repository.article_repository import ArticleRepository
from src.repository.source_repository import SourceRepository
from src.services.universal_scraper import UniversalScraper
from src.core.models import ParserConfig, FetchStatus
from urllib.parse import unquote, parse_qs, urlparse


# 请求间隔（秒）：随机1-3秒，模拟真实用户行为
MIN_DELAY = 1.0
MAX_DELAY = 3.0


async def sync_articles():
    """批量同步所有文章"""
    print("开始批量同步文章...")

    async with get_async_session() as db:
        article_repo = ArticleRepository(db)
        source_repo = SourceRepository(db)

        # 查找所有需要同步的文章
        sql = """
            SELECT id, url, source_id, title
            FROM articles
            WHERE content IS NULL OR length(content) < 100
            ORDER BY id ASC
        """
        articles = await article_repo.fetch_all(sql, {})

        total = len(articles)
        print(f"找到 {total} 条需要同步的文章")

        if total == 0:
            print("没有需要同步的文章")
            return

        success_count = 0
        failed_count = 0

        for idx, article in enumerate(articles, 1):
            article_id = article["id"]
            url = article["url"]

            print(f"\n[{idx}/{total}] 处理文章 {article_id}: {article['title'][:50]}")
            print(f"  URL: {url}")

            try:
                # 获取源配置
                source = await source_repo.fetch_by_id(article["source_id"])
                if not source:
                    print(f"  ❌ 源 {article['source_id']} 不存在")
                    failed_count += 1
                    continue

                # 处理 parser_config
                parser_config = source.get("parser_config")
                if isinstance(parser_config, str):
                    parser_config = ParserConfig.model_validate_json(parser_config)
                elif isinstance(parser_config, dict):
                    parser_config = ParserConfig(**parser_config)

                # 解析 DDG URL
                url_to_fetch = url
                if 'duckduckgo.com/l/' in url_to_fetch and 'uddg=' in url_to_fetch:
                    try:
                        parsed = urlparse(url_to_fetch)
                        params = parse_qs(parsed.query)
                        if 'uddg' in params:
                            encoded_url = params['uddg'][0]
                            url_to_fetch = unquote(encoded_url)
                            print(f"  🔓 解析 DDG URL -> {url_to_fetch}")
                    except Exception as e:
                        print(f"  ⚠️  解析 DDG URL 失败: {e}")

                # 爬取文章
                async with UniversalScraper() as scraper:
                    scraped = await scraper.scrape(
                        url=url_to_fetch,
                        parser_config=parser_config or ParserConfig(
                            title_selector="h1",
                            content_selector="article, main",
                        ),
                        source_id=article["source_id"],
                    )

                    # 检查结果
                    if scraped.error:
                        print(f"  ❌ 爬取失败: {scraped.error}")
                        failed_count += 1

                        # 更新为失败状态
                        await article_repo.update(article_id, {
                            "fetch_status": FetchStatus.FAILED.value,
                            "error_msg": scraped.error,
                        })
                    else:
                        # 严格的内容验证
                        content = scraped.content
                        error_msg = None
                        is_valid = True

                        # 1. 检查内容是否为空或太短
                        if not content or len(content) < 50:
                            is_valid = False
                            error_msg = f"内容太短 ({len(content) if content else 0} 字符 < 50)"

                        # 2. 检查是否包含无效内容标记
                        elif any(keyword in content.lower() for keyword in [
                            "javascript", "enable javascript", "请启用 javascript",
                            "请开启javascript", "需要javascript", "enable cookies"
                        ]):
                            is_valid = False
                            error_msg = "内容包含无效标记 (javascript/cookies)"

                        # 3. 检查是否提取到时间
                        elif not scraped.publish_time:
                            is_valid = False
                            error_msg = "未能提取发布时间"

                        # 更新文章内容
                        update_data = {
                            "title": scraped.title or article["title"],
                            "content": content if is_valid else None,
                            "publish_time": scraped.publish_time,
                            "author": scraped.author,
                            "fetch_status": FetchStatus.SUCCESS.value if is_valid else FetchStatus.FAILED.value,
                            "error_msg": None if is_valid else error_msg,
                        }

                        await article_repo.update(article_id, update_data)

                        if is_valid:
                            success_count += 1
                            print(f"  ✅ 成功！")
                            print(f"     内容长度: {len(content)} 字符")
                            print(f"     发布时间: {scraped.publish_time}")
                            print(f"     标题: {scraped.title}")

                            # 立即验证
                            verify = await article_repo.fetch_by_id(article_id)
                            if verify and verify.get("content"):
                                print(f"  ✓ 验证成功，数据库已更新")
                            else:
                                print(f"  ⚠️  警告：数据库更新可能失败")
                        else:
                            failed_count += 1
                            print(f"  ❌ 失败: {error_msg}")
                            if scraped.publish_time:
                                print(f"     (时间: {scraped.publish_time})")

            except Exception as e:
                print(f"  ❌ 处理失败: {e}")
                failed_count += 1

            # 请求间隔，模拟真实用户行为，降低被封禁风险
            if idx < total:
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                print(f"  ⏳ 等待 {delay:.1f} 秒...")
                await asyncio.sleep(delay)

        print(f"\n{'='*60}")
        print(f"同步完成！")
        print(f"总计: {total}")
        print(f"成功: {success_count}")
        print(f"失败: {failed_count}")
        print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(sync_articles())
