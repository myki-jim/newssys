#!/usr/bin/env python3
"""
Newssys 2.0 种子数据注入脚本

注入哈萨克斯坦新闻源：
- Kazinform (哈通社)
- Tengrinews
- Kursiv (经济类)

使用方法:
    python scripts/seed_sources.py
"""

import asyncio
import logging
import os
import sys

import pymysql
from dotenv import load_dotenv

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.config import settings


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 哈萨克斯坦新闻源配置
KAZAKHSTAN_SOURCES = [
    {
        "site_name": "Kazinform (哈通社)",
        "base_url": "https://www.inform.kz",
        "sitemap_url": "https://www.inform.kz/sitemap.xml",
        "parser_config": {
            "title_selector": "h1.article-title, h1.title",
            "content_selector": "article.article-content, div.article-text, div.content",
            "publish_time_selector": "time.publish-time, time.article-time, time.datetime",
            "author_selector": "span.author, a.author",
            "encoding": "utf-8",
        },
        "enabled": True,
        "crawl_interval": 3600,
        "discovery_method": "sitemap",
    },
    {
        "site_name": "Tengrinews",
        "base_url": "https://tengrinews.kz",
        "sitemap_url": "https://tengrinews.kz/sitemap.xml",
        "parser_config": {
            "title_selector": "h1.article-title, h1.tn-article-title",
            "content_selector": "div.article-content, div.tn-content, article",
            "publish_time_selector": "time.date, time.published, time.datetime",
            "author_selector": "span.author, a.author-link",
            "encoding": "utf-8",
        },
        "enabled": True,
        "crawl_interval": 3600,
        "discovery_method": "sitemap",
    },
    {
        "site_name": "Kursiv (经济类)",
        "base_url": "https://kursiv.kz",
        "sitemap_url": "https://kursiv.kz/sitemap.xml",
        "parser_config": {
            "title_selector": "h1.article-title, h1.entry-title",
            "content_selector": "div.article-content, div.entry-content, article",
            "publish_time_selector": "time.published, time.post-date",
            "author_selector": "span.author, a.author-name",
            "encoding": "utf-8",
        },
        "enabled": True,
        "crawl_interval": 3600,
        "discovery_method": "sitemap",
    },
]


def get_connection():
    """获取数据库连接"""
    return pymysql.connect(
        host=settings.database.host,
        port=settings.database.port,
        user=settings.database.user,
        password=settings.database.password,
        database=settings.database.name,
        charset=settings.database.charset,
    )


def source_exists(base_url: str) -> bool:
    """检查源是否已存在"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT id FROM crawl_sources WHERE base_url = %s",
            (base_url,)
        )
        result = cursor.fetchone()
        return result is not None
    finally:
        cursor.close()
        conn.close()


def insert_source(source_config: dict) -> int | None:
    """插入源配置"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        import json

        sql = """
            INSERT INTO crawl_sources (
                site_name, base_url, parser_config,
                enabled, crawl_interval, discovery_method,
                sitemap_url, robots_status
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
        """

        cursor.execute(sql, (
            source_config["site_name"],
            source_config["base_url"],
            json.dumps(source_config["parser_config"], ensure_ascii=False),
            1 if source_config["enabled"] else 0,
            source_config["crawl_interval"],
            source_config["discovery_method"],
            source_config.get("sitemap_url"),
            "pending",
        ))

        conn.commit()
        source_id = cursor.lastrowid

        logger.info(f"Inserted source: {source_config['site_name']} (ID: {source_id})")
        return source_id

    except pymysql.Error as e:
        logger.error(f"Failed to insert source {source_config['site_name']}: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def main():
    """主函数"""
    load_dotenv()

    logger.info("=" * 60)
    logger.info("Newssys 2.0 - Seeding Kazakhstan News Sources")
    logger.info("=" * 60)

    inserted_count = 0
    skipped_count = 0

    for source_config in KAZAKHSTAN_SOURCES:
        base_url = source_config["base_url"]

        # 检查是否已存在
        if source_exists(base_url):
            logger.info(f"Source already exists: {source_config['site_name']}")
            skipped_count += 1
            continue

        # 插入新源
        source_id = insert_source(source_config)
        if source_id:
            inserted_count += 1

    logger.info("=" * 60)
    logger.info(f"Seeding completed: {inserted_count} inserted, {skipped_count} skipped")
    logger.info("=" * 60)

    # 显示所有源
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, site_name, base_url, enabled, discovery_method FROM crawl_sources")
    sources = cursor.fetchall()

    logger.info("\nCurrent sources in database:")
    for source in sources:
        logger.info(f"  [{source[0]}] {source[1]} - {source[2]} ({'Enabled' if source[3] else 'Disabled'})")

    cursor.close()
    conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
