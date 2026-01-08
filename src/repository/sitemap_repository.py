"""
Sitemap Repository 模块
负责 Sitemap 数据的持久化操作
"""

import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Sitemap, SitemapCreate, SitemapFetchStatus, SitemapUpdate
from src.repository.base import BaseRepository


class SitemapRepository(BaseRepository):
    """
    Sitemap 数据访问层
    处理 Sitemap 的存储、查询和更新
    """

    TABLE_NAME = "sitemaps"

    def __init__(self, session: AsyncSession | None = None) -> None:
        """初始化 SitemapRepository"""
        super().__init__(session)

    async def create(self, sitemap: SitemapCreate) -> int | None:
        """
        创建新 Sitemap

        Args:
            sitemap: Sitemap 创建数据

        Returns:
            新插入的 Sitemap ID
        """
        data = {
            "source_id": sitemap.source_id,
            "url": sitemap.url,
            "fetch_status": SitemapFetchStatus.PENDING.value,
            "article_count": 0,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        return await self.insert(self.TABLE_NAME, data, returning="id")

    async def get_by_id(self, sitemap_id: int) -> dict[str, Any] | None:
        """
        根据 ID 获取 Sitemap

        Args:
            sitemap_id: Sitemap ID

        Returns:
            Sitemap 数据字典
        """
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE id = :id"
        return await self.fetch_one(sql, {"id": sitemap_id})

    async def get_by_source(self, source_id: int) -> list[dict[str, Any]]:
        """
        获取指定源的所有 Sitemap

        Args:
            source_id: 源 ID

        Returns:
            Sitemap 列表
        """
        sql = f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE source_id = :source_id
            ORDER BY created_at DESC
        """
        return await self.fetch_all(sql, {"source_id": source_id})

    async def get_by_url(self, url: str) -> dict[str, Any] | None:
        """
        根据 URL 获取 Sitemap

        Args:
            url: Sitemap URL

        Returns:
            Sitemap 数据字典
        """
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE url = :url"
        return await self.fetch_one(sql, {"url": url})

    async def update_by_id(
        self, sitemap_id: int, update: SitemapUpdate
    ) -> int:
        """
        更新 Sitemap

        Args:
            sitemap_id: Sitemap ID
            update: 更新数据

        Returns:
            影响的行数
        """
        data: dict[str, Any] = {"updated_at": datetime.now()}

        if update.url is not None:
            data["url"] = update.url
        if update.fetch_status is not None:
            data["fetch_status"] = update.fetch_status.value
        if update.article_count is not None:
            data["article_count"] = update.article_count

        return await self.update(
            self.TABLE_NAME, data, "id = :id", {"id": sitemap_id}
        )

    async def delete_by_id(self, sitemap_id: int) -> int:
        """
        删除 Sitemap

        Args:
            sitemap_id: Sitemap ID

        Returns:
            影响的行数
        """
        return await super().delete(self.TABLE_NAME, "id = :id", {"id": sitemap_id})

    async def count_by_source(self, source_id: int) -> int:
        """
        统计指定源的 Sitemap 数量

        Args:
            source_id: 源 ID

        Returns:
            Sitemap 数量
        """
        return await self.count(
            self.TABLE_NAME, "source_id = :source_id", {"source_id": source_id}
        )

    async def update_last_fetched(self, sitemap_id: int) -> int:
        """
        更新最后抓取时间

        Args:
            sitemap_id: Sitemap ID

        Returns:
            影响的行数
        """
        data = {
            "last_fetched": datetime.now(),
            "updated_at": datetime.now(),
        }

        return await self.update(
            self.TABLE_NAME, data, "id = :id", {"id": sitemap_id}
        )
