#!/usr/bin/env python3
"""
数据库备份脚本
备份数据库到指定目录，支持自动清理旧备份
"""

import argparse
import gzip
import os
import shutil
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
os.chdir(PROJECT_ROOT)

from src.core.config import DatabaseSettings


def backup_database(backup_dir: str | None = None, keep_days: int = 7) -> str:
    """
    备份数据库

    Args:
        backup_dir: 备份目录，默认为项目根目录下的 backups 文件夹
        keep_days: 保留最近几天的备份，默认7天

    Returns:
        备份文件路径
    """
    db_config = DatabaseSettings()

    if db_config.type == "sqlite":
        # SQLite 备份
        db_path = PROJECT_ROOT / f"{db_config.name}.db"

        if not db_path.exists():
            raise FileNotFoundError(f"数据库文件不存在: {db_path}")

        # 设置备份目录
        if backup_dir is None:
            backup_dir = PROJECT_ROOT / "backups"
        else:
            backup_dir = Path(backup_dir)

        backup_dir.mkdir(parents=True, exist_ok=True)

        # 生成备份文件名（带时间戳）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{db_config.name}_{timestamp}.db.gz"
        backup_path = backup_dir / backup_filename

        print(f"开始备份数据库...")
        print(f"源文件: {db_path}")
        print(f"备份文件: {backup_path}")
        print(f"数据库大小: {db_path.stat().st_size / 1024 / 1024:.2f} MB")

        # 压缩备份
        with open(db_path, 'rb') as f_in:
            with gzip.open(backup_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        backup_size = backup_path.stat().st_size / 1024 / 1024
        print(f"备份完成! 压缩后大小: {backup_size:.2f} MB")
        print(f"压缩率: {(1 - backup_size / (db_path.stat().st_size / 1024 / 1024)) * 100:.1f}%")

        # 清理旧备份
        clean_old_backups(backup_dir, keep_days)

        return str(backup_path)

    else:
        # MySQL 备份
        import subprocess

        backup_dir = Path(backup_dir) if backup_dir else PROJECT_ROOT / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{db_config.name}_{timestamp}.sql.gz"
        backup_path = backup_dir / backup_filename

        print(f"开始备份 MySQL 数据库...")
        print(f"数据库: {db_config.name}")
        print(f"备份文件: {backup_path}")

        # 使用 mysqldump 备份
        cmd = [
            "mysqldump",
            f"-h{db_config.host}",
            f"-P{db_config.port}",
            f"-u{db_config.user}",
            f"-p{db_config.password}",
            db_config.name,
        ]

        try:
            with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(proc.stdout, f_out)

            print(f"MySQL 备份完成: {backup_path}")
            clean_old_backups(backup_dir, keep_days)
            return str(backup_path)

        except FileNotFoundError:
            raise RuntimeError("mysqldump 命令未找到，请确保已安装 MySQL 客户端")


def clean_old_backups(backup_dir: Path, keep_days: int) -> None:
    """清理超过指定天数的旧备份"""
    if keep_days <= 0:
        return

    now = datetime.now()
    deleted_count = 0

    for backup_file in backup_dir.glob(f"*.db.gz"):
        # 从文件名提取日期
        try:
            parts = backup_file.stem.split('_')
            if len(parts) >= 2:
                date_str = parts[1]  # 20240107_123456
                file_date = datetime.strptime(date_str, "%Y%m%d_%H%M%S")

                # 计算天数差
                delta = (now - file_date).days

                if delta > keep_days:
                    backup_file.unlink()
                    deleted_count += 1
                    print(f"已删除旧备份: {backup_file.name}")
        except (ValueError, IndexError):
            continue

    if deleted_count > 0:
        print(f"共删除 {deleted_count} 个超过 {keep_days} 天的旧备份")


def list_backups(backup_dir: str | None = None) -> None:
    """列出所有备份文件"""
    db_config = DatabaseSettings()

    if backup_dir is None:
        backup_dir = PROJECT_ROOT / "backups"
    else:
        backup_dir = Path(backup_dir)

    if not backup_dir.exists():
        print(f"备份目录不存在: {backup_dir}")
        return

    ext = "*.sql.gz" if db_config.type == "mysql" else "*.db.gz"
    backups = sorted(backup_dir.glob(ext), reverse=True)

    if not backups:
        print("没有找到备份文件")
        return

    print(f"\n找到 {len(backups)} 个备份文件:\n")
    for backup in backups:
        size_mb = backup.stat().st_size / 1024 / 1024
        mtime = datetime.fromtimestamp(backup.stat().st_mtime)
        print(f"  {backup.name:50} {size_mb:8.2f} MB  {mtime.strftime('%Y-%m-%d %H:%M:%S')}")


def restore_database(backup_path: str) -> None:
    """从备份恢复数据库"""
    db_config = DatabaseSettings()
    backup_file = Path(backup_path)

    if not backup_file.exists():
        raise FileNotFoundError(f"备份文件不存在: {backup_file}")

    print(f"警告: 即将恢复数据库，这将覆盖当前数据!")
    response = input("确认继续? (yes/no): ")

    if response.lower() != "yes":
        print("已取消")
        return

    if db_config.type == "sqlite":
        db_path = PROJECT_ROOT / f"{db_config.name}.db"

        print(f"正在恢复数据库...")
        print(f"备份文件: {backup_file}")
        print(f"目标文件: {db_path}")

        # 解压缩并恢复
        with gzip.open(backup_file, 'rb') as f_in:
            with open(db_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        print("数据库恢复完成!")

    else:
        raise NotImplementedError("MySQL 恢复功能待实现")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="数据库备份工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # 备份命令
    backup_parser = subparsers.add_parser("backup", help="备份数据库")
    backup_parser.add_argument("--dir", "-d", help="备份目录")
    backup_parser.add_argument("--keep", "-k", type=int, default=7, help="保留最近几天的备份")

    # 列出命令
    list_parser = subparsers.add_parser("list", help="列出所有备份")
    list_parser.add_argument("--dir", "-d", help="备份目录")

    # 恢复命令
    restore_parser = subparsers.add_parser("restore", help="从备份恢复数据库")
    restore_parser.add_argument("backup", help="备份文件路径")

    args = parser.parse_args()

    if args.command == "backup":
        backup_path = backup_database(args.dir, args.keep)
        print(f"\n备份文件: {backup_path}")

    elif args.command == "list":
        list_backups(args.dir)

    elif args.command == "restore":
        restore_database(args.backup)

    else:
        parser.print_help()
