#!/usr/bin/env python3
"""
添加定时任务和搜索关键词表
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from aiosqlite import Connection
from src.core.config import DatabaseSettings


async def migrate(conn: Connection) -> None:
    """执行数据库迁移"""

    # 创建定时任务表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            schedule_type VARCHAR(50) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'active',
            interval_minutes INTEGER NOT NULL DEFAULT 60,
            max_executions INTEGER,
            execution_count INTEGER NOT NULL DEFAULT 0,
            config JSON,
            last_run_at DATETIME,
            next_run_at DATETIME,
            last_status VARCHAR(50),
            last_error TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建索引
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_schedules_type
        ON schedules(schedule_type)
    """)

    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_schedules_next_run
        ON schedules(next_run_at)
    """)

    # 创建搜索关键词表
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS search_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword VARCHAR(255) NOT NULL,
            description TEXT,
            time_range VARCHAR(10) NOT NULL DEFAULT 'w',
            max_results INTEGER NOT NULL DEFAULT 10,
            region VARCHAR(10) NOT NULL DEFAULT 'us-en',
            is_active BOOLEAN NOT NULL DEFAULT 1,
            search_count INTEGER NOT NULL DEFAULT 0,
            last_searched_at DATETIME,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建索引
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_search_keywords_keyword
        ON search_keywords(keyword)
    """)

    print("✓ 创建表 schedules")
    print("✓ 创建表 search_keywords")
    print("✓ 创建索引")


async def main() -> None:
    """主函数"""
    db_config = DatabaseSettings()

    if db_config.type == "sqlite":
        # 解析数据库URL获取路径
        url = db_config.url
        # sqlite+aiosqlite:////path/to/db.db 或 sqlite+aiosqlite:///path/to/db.db
        if "sqlite+aiosqlite:///" in url:
            # 移除协议前缀，处理绝对路径
            db_path_str = url.split("sqlite+aiosqlite:///")[-1]
            # 如果是绝对路径（以/开头），保持不变
            if db_path_str.startswith("/"):
                db_path = Path(db_path_str)
            else:
                db_path = PROJECT_ROOT / db_path_str
        else:
            print(f"无法解析数据库URL: {url}")
            return

        if not db_path.exists():
            print(f"数据库文件不存在: {db_path}")
            return

        print(f"开始迁移数据库: {db_path}")

        from aiosqlite import connect

        async with connect(db_path) as conn:
            await migrate(conn)
            await conn.commit()

        print("\n迁移完成!")
    else:
        print("MySQL 暂不支持，请手动执行 SQL:")
        print("请参考 migrate() 函数中的 SQL 语句")


if __name__ == "__main__":
    asyncio.run(main())
