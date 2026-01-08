#!/usr/bin/env python3
"""
Newssys 2.0 全链路测试脚本

测试内容：
1. Sitemap 探测
2. 解析校验
3. AI 预筛选
4. SSE 连通性

使用方法:
    python scripts/test_pipeline.py
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.config import settings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# 测试 1: Sitemap 探测
# ============================================================================

async def test_sitemap_discovery():
    """测试 Sitemap 探测功能"""
    logger.info("=" * 60)
    logger.info("TEST 1: Sitemap Discovery")
    logger.info("=" * 60)

    sources_to_test = [
        ("https://www.inform.kz/sitemap.xml", "Kazinform"),
        ("https://tengrinews.kz/sitemap.xml", "Tengrinews"),
        ("https://kursiv.kz/sitemap.xml", "Kursiv"),
    ]

    results = {}

    for sitemap_url, site_name in sources_to_test:
        logger.info(f"\nTesting {site_name}: {sitemap_url}")

        try:
            from src.services.sitemap_parser import SitemapParser

            # 限制递归深度和 URL 数量，避免过载
            parser = SitemapParser(max_depth=1, max_urls=100)
            entries = await parser.parse(sitemap_url)

            # 显示前 5 条 URL
            logger.info(f"  Found {len(entries)} entries")
            logger.info("  Latest 5 URLs:")

            for i, entry in enumerate(entries[:5], 1):
                logger.info(f"    {i}. {entry.loc}")
                if entry.lastmod:
                    logger.info(f"       Last modified: {entry.lastmod}")

            results[site_name] = {
                "total": len(entries),
                "sample_urls": [e.loc for e in entries[:5]],
                "success": True,
            }

        except Exception as e:
            logger.error(f"  Failed: {e}")
            results[site_name] = {"success": False, "error": str(e)}

    return results


# ============================================================================
# 测试 2: 解析校验
# ============================================================================

async def test_article_parsing():
    """测试文章解析功能"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Article Parsing")
    logger.info("=" * 60)

    # 使用 Kazinform 的一篇文章进行测试
    test_url = "https://www.inform.kz/"

    logger.info(f"Testing URL: {test_url}")

    try:
        from src.services.universal_scraper import UniversalScraper
        from src.services.time_extractor import TimeExtractor
        from src.core.models import ParserConfig

        scraper = UniversalScraper()
        time_extractor = TimeExtractor()

        # 使用默认解析器配置
        parser_config = ParserConfig(
            title_selector="h1",
            content_selector="article, main",
            encoding="utf-8",
        )

        # 抓取文章
        logger.info("  Fetching article...")
        article = await scraper.scrape(
            url=test_url,
            parser_config=parser_config,
            source_id=1,  # 测试用
        )

        # 时间提取
        logger.info("  Extracting publish time...")
        if article.publish_time is None:
            article.publish_time = time_extractor.extract_publish_time(
                html_content="",
                url=test_url,
            )

        # 显示结果
        logger.info("\n  Results:")
        logger.info(f"    Title: {article.title[:100] if article.title else 'N/A'}...")
        logger.info(f"    Content length: {len(article.content) if article.content else 0} characters")
        logger.info(f"    Content (Markdown): {len(article.content) if article.content else 0} chars")
        logger.info(f"    Publish time: {article.publish_time or 'N/A'}")
        logger.info(f"    Author: {article.author or 'N/A'}")

        return {
            "success": True,
            "title": article.title,
            "content_length": len(article.content) if article.content else 0,
            "publish_time": str(article.publish_time) if article.publish_time else None,
            "author": article.author,
        }

    except Exception as e:
        logger.error(f"  Failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# 测试 3: AI 预筛选
# ============================================================================

async def test_ai_selection():
    """测试 AI 预筛选功能"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: AI-Based Event Selection")
    logger.info("=" * 60)

    # 模拟 10 篇哈萨克斯坦相关文章
    mock_articles = [
        {
            "id": i + 1,
            "title": title,
            "summary": f"Article about {title.lower()}",
            "publish_time": datetime.now().isoformat(),
            "source": "Kazinform",
        }
        for i, title in enumerate([
            "哈萨克斯坦总统签署新数字经济发展法案",
            "阿拉木图举办国际投资论坛",
            "哈国央行下调基准利率至 9.5%",
            "中哈合作建设新物流中心",
            "阿斯塔纳地铁新线路开通",
            "哈萨克斯坦小麦出口量创历史新高",
            "国家石油公司公布季度财报",
            "教育部推出新的职业教育改革",
            "哈萨克斯坦举办世界游牧民族运动会",
            "总理主持内阁会议讨论经济政策",
        ], 1)
    ]

    logger.info(f"Simulated {len(mock_articles)} articles")
    logger.info("  Articles:")
    for article in mock_articles:
        logger.info(f"    [{article['id']}] {article['title']}")

    # 构建提示词
    prompt = f"""你是一位资深新闻编辑。你的任务是从一系列新闻中筛选出最具社会影响力的核心事件。

筛选标准：
1. **社会影响力**：优先选择对社会、政治、经济产生重大影响的事件
2. **新闻价值**：考虑事件的时效性、重要性、接近性
3. **独特性**：避免选择重复或过于相似的事件
4. **深度**：优先选择有深度分析和详细报道的文章

请从以下 {len(mock_articles)} 篇文章中，选择出前 3 个最具影响力的核心事件。

返回格式：
仅返回选中的文章 ID 列表，用逗号分隔，如：1, 5, 12, 23, 45, ...

"""

    for article in mock_articles:
        prompt += f"\n[{article['id']}] {article['title']}\n   摘要：{article['summary']}\n"

    prompt += "\n请基于以上信息，返回选中的文章 ID："

    logger.info("\n  Calling AI API...")
    logger.info(f"  Model: {settings.ai.model}")

    try:
        async with httpx.AsyncClient(timeout=settings.ai.timeout) as client:
            response = await client.post(
                f"{settings.ai.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.ai.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.ai.model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 100,
                    "temperature": settings.ai.temperature,
                },
            )
            response.raise_for_status()
            result = response.json()

            # 提取 AI 返回的 ID
            content = result["choices"][0]["message"]["content"]
            logger.info(f"\n  AI Response: {content}")

            # 解析 ID
            selected_ids = [int(x.strip()) for x in content.split(",") if x.strip().isdigit()]

            logger.info(f"\n  Selected {len(selected_ids)} articles:")
            for article_id in selected_ids:
                article = next((a for a in mock_articles if a["id"] == article_id), None)
                if article:
                    logger.info(f"    [{article_id}] {article['title']}")

            return {
                "success": True,
                "selected_count": len(selected_ids),
                "selected_ids": selected_ids,
                "raw_response": content,
            }

    except Exception as e:
        logger.error(f"  Failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# 测试 4: SSE 连通性
# ============================================================================

async def test_sse_connectivity():
    """测试 SSE 流式响应"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: SSE Stream Connectivity")
    logger.info("=" * 60)

    # 注意：此测试需要 API 服务器正在运行
    api_url = f"http://{settings.api.host}:{settings.api.port}/api/v1/reports/generate"

    logger.info(f"Testing SSE endpoint: {api_url}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            async with client.stream(
                "POST",
                api_url,
                json={
                    "title": "测试报告",
                    "time_range": "week",
                    "max_articles": 5,
                    "enable_search": False,
                },
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status_code != 200:
                    logger.error(f"  HTTP Status: {response.status_code}")
                    logger.error(f"  Response: {await response.aread()}")
                    return {"success": False, "error": f"HTTP {response.status_code}"}

                logger.info("  Connection established, reading stream...")

                event_count = 0
                chunk_count = 0
                start_time = time.time()

                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                        event_count += 1
                        logger.info(f"    Event: {event_type}")

                    elif line.startswith("data:"):
                        try:
                            data = json.loads(line[5:].strip())
                            if data.get("event") == "chunk":
                                chunk_count += 1
                        except:
                            pass

                    # 只读取前 5 个事件进行测试
                    if event_count >= 5:
                        break

                elapsed = time.time() - start_time

                logger.info(f"\n  Results:")
                logger.info(f"    Events received: {event_count}")
                logger.info(f"    Chunks received: {chunk_count}")
                logger.info(f"    Time elapsed: {elapsed:.2f}s")

                return {
                    "success": True,
                    "event_count": event_count,
                    "chunk_count": chunk_count,
                    "elapsed_time": elapsed,
                }

    except httpx.ConnectError:
        logger.warning("  API server not running (this is expected if not started)")
        return {"success": False, "error": "API server not running", "skipped": True}

    except Exception as e:
        logger.error(f"  Failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# 主函数
# ============================================================================

async def main():
    """运行所有测试"""
    load_dotenv()

    logger.info("=" * 60)
    logger.info("Newssys 2.0 - Full Pipeline Test")
    logger.info("=" * 60)
    logger.info(f"Database: {settings.database.host}:{settings.database.port}/{settings.database.name}")
    logger.info(f"AI Model: {settings.ai.model}")
    logger.info("=" * 60)

    results = {}

    # 测试 1: Sitemap 探测
    try:
        results["sitemap"] = await test_sitemap_discovery()
    except Exception as e:
        logger.error(f"Sitemap test failed: {e}")
        results["sitemap"] = {"success": False, "error": str(e)}

    # 测试 2: 解析校验
    try:
        results["parsing"] = await test_article_parsing()
    except Exception as e:
        logger.error(f"Parsing test failed: {e}")
        results["parsing"] = {"success": False, "error": str(e)}

    # 测试 3: AI 预筛选
    try:
        results["ai_selection"] = await test_ai_selection()
    except Exception as e:
        logger.error(f"AI selection test failed: {e}")
        results["ai_selection"] = {"success": False, "error": str(e)}

    # 测试 4: SSE 连通性
    try:
        results["sse"] = await test_sse_connectivity()
    except Exception as e:
        logger.error(f"SSE test failed: {e}")
        results["sse"] = {"success": False, "error": str(e)}

    # 输出总结
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    for test_name, test_result in results.items():
        # 处理嵌套结果（如 sitemap）
        if test_name == "sitemap":
            all_passed = all(v.get("success", False) for v in test_result.values()) if test_result else False
            status = "✓ PASS" if all_passed else "✗ FAIL"
            logger.info(f"  {test_name}: {status}")
            for site, site_result in test_result.items():
                site_status = "✓" if site_result.get("success") else "✗"
                logger.info(f"    {site_status} {site}: {site_result.get('total', 0)} entries")
        else:
            status = "✓ PASS" if test_result.get("success") else "✗ FAIL"
            if test_result.get("skipped"):
                status = "⊘ SKIP"
            logger.info(f"  {test_name}: {status}")

            if not test_result.get("success") and not test_result.get("skipped"):
                logger.info(f"    Error: {test_result.get('error')}")

    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
