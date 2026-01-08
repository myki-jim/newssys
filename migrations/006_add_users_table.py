"""
添加用户表

创建用户系统，支持登录和基本用户管理
"""

from datetime import datetime
from sqlalchemy import text

def upgrade(connection):
    """添加用户表"""
    # 创建用户表
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'user',
            is_active BOOLEAN NOT NULL DEFAULT 1,
            office VARCHAR(50),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))

    # 创建索引
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)
    """))

    # 插入默认 admin 用户
    connection.execute(text("""
        INSERT INTO users (username, password, role, is_active, office)
        VALUES ('admin', 'admin123', 'admin', 1, NULL)
    """))

    # 插入办公室用户 001-007
    offices = [
        ('001', 'pass001'),
        ('002', 'pass002'),
        ('003', 'pass003'),
        ('004', 'pass004'),
        ('005', 'pass005'),
        ('006', 'pass006'),
        ('007', 'pass007'),
    ]

    for office, password in offices:
        connection.execute(text("""
            INSERT INTO users (username, password, role, is_active, office)
            VALUES (:username, :password, 'user', 1, :office)
        """), {"username": office, "password": password, "office": f"办公室{office}"})

def downgrade(connection):
    """删除用户表"""
    connection.execute(text("DROP INDEX IF EXISTS idx_users_username"))
    connection.execute(text("DROP TABLE IF EXISTS users"))
