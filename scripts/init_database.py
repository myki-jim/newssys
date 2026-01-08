#!/usr/bin/env python3
"""
Newssys 2.0 数据库初始化脚本

功能：
1. 创建数据库（如果不存在）
2. 执行 schema.sql
3. 执行 002_schema_stabilization.sql

使用方法:
    python scripts/init_database.py [--force]
"""

import argparse
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


def get_connection_params():
    """获取数据库连接参数（不指定数据库）"""
    return {
        "host": settings.database.host,
        "port": settings.database.port,
        "user": settings.database.user,
        "password": settings.database.password,
        "charset": settings.database.charset,
    }


def create_database_if_not_exists():
    """创建数据库（如果不存在）"""
    params = get_connection_params()

    logger.info(f"Checking database: {settings.database.name}")

    try:
        # 先连接到 MySQL 服务器（不指定数据库）
        conn = pymysql.connect(**params)
        cursor = conn.cursor()

        # 检查数据库是否存在
        cursor.execute(f"SHOW DATABASES LIKE '{settings.database.name}'")
        result = cursor.fetchone()

        if result:
            logger.info(f"Database '{settings.database.name}' already exists")
        else:
            # 创建数据库
            cursor.execute(
                f"CREATE DATABASE `{settings.database.name}` "
                f"DEFAULT CHARACTER SET {settings.database.charset} COLLATE {settings.database.charset}_unicode_ci"
            )
            logger.info(f"Database '{settings.database.name}' created successfully")

        cursor.close()
        conn.close()

        return True

    except pymysql.Error as e:
        logger.error(f"Failed to create database: {e}")
        return False


def execute_sql_file(file_path: str):
    """执行 SQL 文件"""
    params = get_connection_params()
    params["database"] = settings.database.name

    logger.info(f"Executing SQL file: {file_path}")

    try:
        conn = pymysql.connect(**params)
        cursor = conn.cursor()

        # 读取 SQL 文件
        with open(file_path, "r", encoding="utf-8") as f:
            sql_content = f.read()

        # 分割 SQL 语句（处理多条语句）
        # 简单分割，实际可能需要更复杂的解析
        statements = []
        current_statement = []
        in_delimiter = False

        for line in sql_content.split("\n"):
            # 跳过注释
            if line.strip().startswith("--"):
                continue

            # 检查是否是自定义分隔符
            if line.strip().startswith("DELIMITER"):
                in_delimiter = True
                continue

            current_statement.append(line)

            # 检查语句结束
            line_stripped = line.strip()
            if line_stripped.endswith(";") or (
                in_delimiter and line_stripped.endswith("//")
            ):
                statement = "\n".join(current_statement).strip()
                if statement and statement not in (";", "//"):
                    # 清理自定义分隔符标记
                    statement = statement.rstrip(";").rstrip("//")
                    statements.append(statement + ";")
                current_statement = []
                in_delimiter = False

        # 执行每条语句
        success_count = 0
        for i, statement in enumerate(statements):
            if statement.strip():
                try:
                    cursor.execute(statement)
                    success_count += 1
                except pymysql.Error as e:
                    # 某些错误可以忽略（如表已存在）
                    if "Duplicate" not in str(e) and "already exists" not in str(e):
                        logger.warning(f"Statement {i + 1} warning: {e}")

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Executed {success_count}/{len(statements)} statements successfully")
        return True

    except FileNotFoundError:
        logger.error(f"SQL file not found: {file_path}")
        return False
    except pymysql.Error as e:
        logger.error(f"Failed to execute SQL file: {e}")
        return False


def verify_schema():
    """验证数据库表是否创建成功"""
    params = get_connection_params()
    params["database"] = settings.database.name

    try:
        conn = pymysql.connect(**params)
        cursor = conn.cursor()

        # 获取所有表
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = [
            "crawl_sources",
            "articles",
            "reports",
            "report_references",
        ]

        missing_tables = [t for t in expected_tables if t not in tables]

        cursor.close()
        conn.close()

        if missing_tables:
            logger.warning(f"Missing tables: {missing_tables}")
            return False

        logger.info(f"Schema verified successfully. Tables: {tables}")
        return True

    except pymysql.Error as e:
        logger.error(f"Failed to verify schema: {e}")
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Initialize Newssys 2.0 database")
    parser.add_argument("--force", action="store_true", help="Force re-initialization")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Newssys 2.0 Database Initialization")
    logger.info("=" * 60)

    # 步骤 1: 创建数据库
    if not create_database_if_not_exists():
        logger.error("Failed to create database")
        return 1

    # 步骤 2: 执行 schema.sql
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "schema.sql"
    )

    if not os.path.exists(schema_path):
        logger.error(f"Schema file not found: {schema_path}")
        return 1

    if not execute_sql_file(schema_path):
        logger.error("Failed to execute schema.sql")
        return 1

    # 步骤 3: 执行 002_schema_stabilization.sql
    migration_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "migrations", "002_schema_stabilization.sql"
    )

    if not os.path.exists(migration_path):
        logger.warning(f"Migration file not found: {migration_path}")
    else:
        if not execute_sql_file(migration_path):
            logger.error("Failed to execute 002_schema_stabilization.sql")
            return 1

    # 步骤 4: 验证
    if not verify_schema():
        logger.error("Schema verification failed")
        return 1

    logger.info("=" * 60)
    logger.info("Database initialization completed successfully!")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    load_dotenv()
    sys.exit(main())
