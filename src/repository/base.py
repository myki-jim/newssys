"""
Repository 基类模块
定义泛型 Repository 基础接口
"""

from collections.abc import AsyncGenerator
from typing import Any, TypeVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# 兼容 SQLAlchemy 1.4 和 2.0
try:
    from sqlalchemy.orm import Row, RowMapping
except ImportError:
    # SQLAlchemy 1.4
    from sqlalchemy.engine import Row
    RowMapping = Any

from src.infrastructure.database import get_db_session


T = TypeVar("T")

# 类型别名：Row 的泛型版本
RowAny = Row[Any]


class BaseRepository:
    """
    Repository 泛型基类
    提供通用的数据库操作方法
    """

    def __init__(self, session: AsyncSession | None = None) -> None:
        """
        初始化 Repository

        Args:
            session: 数据库会话，为空时自动创建
        """
        self._session = session
        self._owns_session = session is None

    @property
    def session(self) -> AsyncSession:
        """获取数据库会话"""
        if self._session is None:
            raise RuntimeError("Session not available")
        return self._session

    async def __aenter__(self) -> "BaseRepository":
        """异步上下文管理器入口"""
        if self._owns_session:
            self._session = await get_db_session().__anext__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """异步上下文管理器退出"""
        if self._owns_session and self._session is not None:
            await self._session.close()

    async def execute(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> RowAny:
        """
        执行 SQL 语句

        Args:
            sql: SQL 语句
            params: 查询参数

        Returns:
            查询结果
        """
        result = await self.session.execute(text(sql), params or {})
        return result

    async def fetch_all(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> list[RowMapping]:
        """
        获取所有结果

        Args:
            sql: SQL 语句
            params: 查询参数

        Returns:
            结果列表
        """
        result = await self.execute(sql, params)
        return result.mappings().all()

    async def fetch_one(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> RowMapping | None:
        """
        获取单条结果

        Args:
            sql: SQL 语句
            params: 查询参数

        Returns:
            单条结果或 None
        """
        result = await self.execute(sql, params)
        return result.mappings().first()

    async def fetch_val(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
        column: int | str = 0,
    ) -> Any | None:
        """
        获取单个值

        Args:
            sql: SQL 语句
            params: 查询参数
            column: 列索引或列名

        Returns:
            单个值或 None
        """
        result = await self.execute(sql, params)
        row = result.first()
        if row is None:
            return None
        if isinstance(column, int):
            return row[column]
        return row._mapping[column]

    async def execute_write(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> int:
        """
        执行写操作（INSERT/UPDATE/DELETE）

        Args:
            sql: SQL 语句
            params: 查询参数

        Returns:
            影响的行数
        """
        result = await self.execute(sql, params)
        await self.session.commit()
        return result.rowcount

    async def insert(
        self, table: str, data: dict[str, Any], returning: str | None = None
    ) -> Any:
        """
        插入数据

        Args:
            table: 表名
            data: 数据字典
            returning: 返回字段（如 "id" 或 "*" 返回所有列）

        Returns:
            插入的 ID、指定字段值，或完整行字典（当 returning="*"）
        """
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f":{k}" for k in data.keys())
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        if returning:
            sql += f" RETURNING {returning}"
            result = await self.execute(sql, data)
            if returning == "*":
                # Return full row as dict
                row = result.mappings().first()
                await self.session.commit()
                return dict(row) if row else None
            else:
                # Return single column value
                row = result.first()
                await self.session.commit()
                return row[0] if row else None
        else:
            await self.execute(sql, data)
            await self.session.commit()
            return None

    async def insert_many(
        self, table: str, data_list: list[dict[str, Any]]
    ) -> int:
        """
        批量插入数据

        Args:
            table: 表名
            data_list: 数据字典列表

        Returns:
            插入的行数
        """
        if not data_list:
            return 0

        columns = ", ".join(data_list[0].keys())
        placeholders = ", ".join(f":{k}" for k in data_list[0].keys())
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        for data in data_list:
            await self.execute(sql, data)

        await self.session.commit()
        return len(data_list)

    async def update(
        self,
        table: str,
        data: dict[str, Any],
        where: str,
        where_params: dict[str, Any] | None = None,
    ) -> int:
        """
        更新数据

        Args:
            table: 表名
            data: 更新数据字典
            where: WHERE 条件
            where_params: WHERE 参数

        Returns:
            影响的行数
        """
        set_clause = ", ".join(f"{k} = :{k}" for k in data.keys())
        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"

        params = {**data, **(where_params or {})}
        return await self.execute_write(sql, params)

    async def delete(
        self, table: str, where: str, params: dict[str, Any] | None = None
    ) -> int:
        """
        删除数据

        Args:
            table: 表名
            where: WHERE 条件
            params: 查询参数

        Returns:
            影响的行数
        """
        sql = f"DELETE FROM {table} WHERE {where}"
        return await self.execute_write(sql, params)

    async def count(
        self, table: str, where: str | None = None, params: dict[str, Any] | None = None
    ) -> int:
        """
        统计行数

        Args:
            table: 表名
            where: WHERE 条件
            params: 查询参数

        Returns:
            行数
        """
        sql = f"SELECT COUNT(*) as count FROM {table}"
        if where:
            sql += f" WHERE {where}"

        result = await self.fetch_val(sql, params, "count")
        return int(result) if result is not None else 0

    async def exists(
        self, table: str, where: str, params: dict[str, Any] | None = None
    ) -> bool:
        """
        检查记录是否存在

        Args:
            table: 表名
            where: WHERE 条件
            params: 查询参数

        Returns:
            是否存在
        """
        sql = f"SELECT 1 FROM {table} WHERE {where} LIMIT 1"
        result = await self.fetch_val(sql, params)
        return result is not None
