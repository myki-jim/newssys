"""
爬虫源 Repository 模块
负责爬虫源配置的持久化操作
"""

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import CrawlSource, ParserConfig, SourceCreate, SourceUpdate
from src.repository.base import BaseRepository


class SourceRepository(BaseRepository):
    """
    爬虫源数据访问层
    处理爬虫源配置的增删改查
    """

    TABLE_NAME = "crawl_sources"

    def __init__(self, session: AsyncSession) -> None:
        """初始化 SourceRepository"""
        super().__init__(session)

    @staticmethod
    def _serialize_parser_config(config: ParserConfig) -> str:
        """
        序列化解析器配置

        Args:
            config: ParserConfig 对象

        Returns:
            JSON 字符串
        """
        return config.model_dump_json()

    @staticmethod
    def _deserialize_parser_config(config_str: str) -> ParserConfig:
        """
        反序列化解析器配置

        Args:
            config_str: JSON 字符串

        Returns:
            ParserConfig 对象
        """
        return ParserConfig.model_validate_json(config_str)

    # ========================================================================
    # BaseRepository 方法适配
    # ========================================================================

    async def create(self, source: SourceCreate) -> dict[str, Any]:
        """
        创建新的爬虫源

        Args:
            source: 爬虫源创建数据

        Returns:
            新插入记录的字典
        """
        now = datetime.now()

        data = {
            "site_name": source.site_name,
            "base_url": source.base_url,
            "parser_config": self._serialize_parser_config(source.parser_config),
            "enabled": 1 if source.enabled else 0,
            "crawl_interval": source.crawl_interval,
            "robots_status": source.robots_status.value if hasattr(source.robots_status, 'value') else str(source.robots_status),
            "discovery_method": source.discovery_method,
            "success_count": 0,
            "failure_count": 0,
            "created_at": now,
            "updated_at": now,
        }

        return await self.insert(self.TABLE_NAME, data, returning="*")

    async def fetch_by_id(self, source_id: int) -> dict[str, Any] | None:
        """
        根据 ID 获取爬虫源

        Args:
            source_id: 爬虫源 ID

        Returns:
            爬虫源数据字典，不存在时返回 None
        """
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE id = :id"
        result = await self.fetch_one(sql, {"id": source_id})
        if result and "parser_config" in result and result["parser_config"]:
            result = dict(result)
            result["parser_config"] = self._deserialize_parser_config(result["parser_config"])
            result["enabled"] = bool(result["enabled"])
            return result
        return result

    async def fetch_by_base_url(self, base_url: str) -> dict[str, Any] | None:
        """
        根据 base_url 获取爬虫源

        Args:
            base_url: 基础 URL

        Returns:
            爬虫源数据字典，不存在时返回 None
        """
        # 尝试精确匹配
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE base_url = :base_url"
        result = await self.fetch_one(sql, {"base_url": base_url})

        if result:
            return dict(result)

        # 尝试带/或不带/的匹配（SQLite 兼容语法）
        base_url_normalized = base_url.rstrip("/")
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE TRIM(base_url, '/') = :base_url"
        result = await self.fetch_one(sql, {"base_url": base_url_normalized})

        return dict(result) if result else None

    async def fetch_many(
        self,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at DESC",
    ) -> list[dict[str, Any]]:
        """
        获取爬虫源列表

        Args:
            filters: 筛选条件
            limit: 返回数量限制
            offset: 偏移量
            order_by: 排序

        Returns:
            爬虫源列表
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        where_clause = []

        if filters:
            if "enabled" in filters:
                where_clause.append("enabled = :enabled")
                params["enabled"] = 1 if filters["enabled"] else 0
            if "discovery_method" in filters:
                where_clause.append("discovery_method = :discovery_method")
                params["discovery_method"] = filters["discovery_method"]
            if "robots_status" in filters:
                where_clause.append("robots_status = :robots_status")
                params["robots_status"] = filters["robots_status"]

        sql = f"SELECT * FROM {self.TABLE_NAME}"

        if where_clause:
            sql += " WHERE " + " AND ".join(where_clause)

        sql += f" ORDER BY {order_by} LIMIT :limit OFFSET :offset"

        results = await self.fetch_all(sql, params)

        # 反序列化 parser_config
        output = []
        for result in results:
            row = dict(result)
            if "parser_config" in row and row["parser_config"]:
                row["parser_config"] = self._deserialize_parser_config(row["parser_config"])
            row["enabled"] = bool(row["enabled"])
            output.append(row)

        return output

    async def update(self, source_id: int, data: dict[str, Any] | SourceUpdate) -> dict[str, Any]:
        """
        更新爬虫源配置

        Args:
            source_id: 爬虫源 ID
            data: 更新数据

        Returns:
            更新后的爬虫源
        """
        update_data: dict[str, Any] = {"updated_at": datetime.now()}

        if isinstance(data, SourceUpdate):
            if data.site_name is not None:
                update_data["site_name"] = data.site_name
            if data.base_url is not None:
                update_data["base_url"] = data.base_url
            if data.parser_config is not None:
                update_data["parser_config"] = self._serialize_parser_config(data.parser_config)
            if data.enabled is not None:
                update_data["enabled"] = 1 if data.enabled else 0
            if data.crawl_interval is not None:
                update_data["crawl_interval"] = data.crawl_interval
        else:
            update_data.update(data)
            if "parser_config" in update_data and isinstance(update_data["parser_config"], ParserConfig):
                update_data["parser_config"] = self._serialize_parser_config(update_data["parser_config"])
            if "enabled" in update_data and isinstance(update_data["enabled"], bool):
                update_data["enabled"] = 1 if update_data["enabled"] else 0
            if "robots_status" in update_data and hasattr(update_data["robots_status"], "value"):
                update_data["robots_status"] = update_data["robots_status"].value

        return await self.update_by_id(source_id, update_data)

    async def update_by_id(self, source_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """执行更新"""
        set_clauses = [f"{k} = :_{k}" for k in data.keys()]
        placeholders = {f"_{k}": v for k, v in data.items()}
        placeholders["_id"] = source_id

        sql = f"""
            UPDATE {self.TABLE_NAME}
            SET {', '.join(set_clauses)}
            WHERE id = :_id
            RETURNING *
        """

        result = await self.fetch_one(sql, placeholders)

        if result and "parser_config" in result and result["parser_config"]:
            result["parser_config"] = self._deserialize_parser_config(result["parser_config"])
            result["enabled"] = bool(result["enabled"])

        return dict(result) if result else await self.fetch_by_id(source_id)  # type: ignore

    async def delete(self, source_id: int) -> bool:
        """
        删除爬虫源

        Args:
            source_id: 爬虫源 ID

        Returns:
            是否成功
        """
        await self.delete_by_id(source_id)
        return True

    async def delete_by_id(self, source_id: int) -> int:
        """删除爬虫源（实现）"""
        return await self.delete(self.TABLE_NAME, "id = :id", {"id": source_id})

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        """
        统计爬虫源数量

        Args:
            filters: 筛选条件

        Returns:
            爬虫源数量
        """
        params: dict[str, Any] = {}
        where_clause = []

        if filters:
            if "enabled" in filters:
                where_clause.append("enabled = :enabled")
                params["enabled"] = 1 if filters["enabled"] else 0

        sql = f"SELECT COUNT(*) as count FROM {self.TABLE_NAME}"

        if where_clause:
            sql += " WHERE " + " AND ".join(where_clause)

        result = await self.fetch_one(sql, params)
        return result["count"] if result else 0

    # ========================================================================
    # 统计方法
    # ========================================================================

    async def get_stats(self, start_date: datetime | None = None) -> list[dict[str, Any]]:
        """
        获取源统计数据

        Args:
            start_date: 统计开始时间

        Returns:
            统计数据列表
        """
        sql = """
            SELECT
                s.id as source_id,
                s.site_name,
                COUNT(a.id) as total_articles,
                SUM(CASE WHEN a.status = 'processed' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN a.status = 'failed' THEN 1 ELSE 0 END) as failure_count,
                MAX(a.created_at) as last_crawled_at
            FROM crawl_sources s
            LEFT JOIN articles a ON s.id = a.source_id
        """

        params: dict[str, Any] = {}

        if start_date:
            sql += " AND a.created_at >= :start_date"
            params["start_date"] = start_date

        sql += """
            GROUP BY s.id, s.site_name
            ORDER BY total_articles DESC
        """

        results = await self.fetch_all(sql, params)

        stats = []
        for r in results:
            total = r["total_articles"] or 0
            success = r["success_count"] or 0
            failure = r["failure_count"] or 0

            stats.append({
                "source_id": r["source_id"],
                "site_name": r["site_name"],
                "total_articles": total,
                "success_count": success,
                "failure_count": failure,
                "success_rate": round(success / total * 100, 2) if total > 0 else 0,
                "last_crawled_at": r["last_crawled_at"],
            })

        return stats

    # ========================================================================
    # 领域模型转换
    # ========================================================================

    def to_domain_model(self, row: dict[str, Any]) -> CrawlSource:
        """
        将数据库记录转换为领域模型

        Args:
            row: 数据库记录字典

        Returns:
            CrawlSource 对象
        """
        parser_config = (
            self._deserialize_parser_config(row["parser_config"])
            if isinstance(row["parser_config"], str)
            else row["parser_config"]
        )

        return CrawlSource(
            id=row["id"],
            site_name=row["site_name"],
            base_url=row["base_url"],
            parser_config=parser_config,
            enabled=bool(row["enabled"]),
            crawl_interval=row["crawl_interval"],
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    async def get_domain_by_id(self, source_id: int) -> CrawlSource | None:
        """
        根据 ID 获取爬虫源领域模型

        Args:
            source_id: 爬虫源 ID

        Returns:
            CrawlSource 对象，不存在时返回 None
        """
        row = await self.fetch_by_id(source_id)
        if row is None:
            return None
        return self.to_domain_model(row)
