#!/usr/bin/env python3
"""
创建 Sitemap 相关数据库表
"""

import asyncio
import sys
sys.path.insert(0, '/Users/jimmyki/Documents/Code/news')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.core.orm_models import Base, SitemapOrm, PendingArticleOrm
from src.core.config import settings


async def init_tables():
    """创建数据库表"""

    # 使用实际配置的数据库
    engine = create_async_engine(
        settings.database.url,
        echo=True,
    )

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("✓ 数据库表创建成功！")
    print(f"  数据库: {settings.database.url}")
    print(f"  - sitemaps")
    print(f"  - pending_articles")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_tables())
