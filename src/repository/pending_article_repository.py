"""
PendingArticle Repository 模块
负责待爬文章数据的持久化操作
"""

import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import (
    PendingArticle,
    PendingArticleCreate,
    PendingArticleStatus,
)
from src.repository.base import BaseRepository


class PendingArticleRepository(BaseRepository):
    """
    待爬文章数据访问层
    处理待爬文章的存储、查询和更新
    """

    TABLE_NAME = "pending_articles"

    def __init__(self, session: AsyncSession | None = None) -> None:
        """初始化 PendingArticleRepository"""
        super().__init__(session)

    @staticmethod
    def _generate_url_hash(url: str) -> str:
        """
        生成 URL 哈希值用于去重

        Args:
            url: 文章 URL

        Returns:
            URL 的 MD5 哈希值
        """
        return hashlib.md5(url.encode("utf-8")).hexdigest()

    async def create(self, article: PendingArticleCreate) -> int | None:
        """
        创建待爬文章

        Args:
            article: 待爬文章创建数据

        Returns:
            新插入的文章 ID
        """
        url_hash = self._generate_url_hash(article.url)

        data = {
            "source_id": article.source_id,
            "sitemap_id": article.sitemap_id,
            "url": article.url,
            "url_hash": url_hash,
            "title": article.title,
            "publish_time": article.publish_time,
            "status": PendingArticleStatus.PENDING.value,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        return await self.insert(self.TABLE_NAME, data, returning="id")

    async def batch_create(
        self, articles: list[PendingArticleCreate]
    ) -> int:
        """
        批量创建待爬文章

        Args:
            articles: 待爬文章创建数据列表

        Returns:
            成功插入的文章数量
        """
        if not articles:
            return 0

        now = datetime.now()
        data_list = []

        for article in articles:
            url_hash = self._generate_url_hash(article.url)
            data_list.append({
                "source_id": article.source_id,
                "sitemap_id": article.sitemap_id,
                "url": article.url,
                "url_hash": url_hash,
                "title": article.title,
                "publish_time": article.publish_time,
                "status": PendingArticleStatus.PENDING.value,
                "created_at": now,
                "updated_at": now,
            })

        return await self.insert_many(self.TABLE_NAME, data_list)

    async def get_by_id(self, article_id: int) -> dict[str, Any] | None:
        """
        根据 ID 获取待爬文章

        Args:
            article_id: 文章 ID

        Returns:
            文章数据字典
        """
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE id = :id"
        return await self.fetch_one(sql, {"id": article_id})

    async def get_by_source(
        self,
        source_id: int,
        status: PendingArticleStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        获取指定源的待爬文章（自动过滤低质量文章）

        按发布时间倒序排列（最新的优先），没有发布时间的排在最后

        Args:
            source_id: 源 ID
            status: 文章状态（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            文章列表
        """
        params: dict[str, Any] = {"source_id": source_id, "limit": limit, "offset": offset}
        where_clause = "source_id = :source_id AND status != 'low_quality'"

        if status is not None:
            where_clause += " AND status = :status"
            params["status"] = status.value

        sql = f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE {where_clause}
            ORDER BY publish_time DESC NULLS LAST, created_at DESC
            LIMIT :limit OFFSET :offset
        """

        return await self.fetch_all(sql, params)

    async def get_by_sitemap(
        self,
        sitemap_id: int,
        status: PendingArticleStatus | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取指定 Sitemap 的待爬文章（自动过滤低质量文章）

        按发布时间倒序排列（最新的优先），没有发布时间的排在最后

        Args:
            sitemap_id: Sitemap ID
            status: 文章状态（可选）

        Returns:
            文章列表
        """
        params: dict[str, Any] = {"sitemap_id": sitemap_id}
        where_clause = "sitemap_id = :sitemap_id AND status != 'low_quality'"

        if status is not None:
            where_clause += " AND status = :status"
            params["status"] = status.value

        sql = f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE {where_clause}
            ORDER BY publish_time DESC NULLS LAST, created_at DESC
        """

        return await self.fetch_all(sql, params)

    async def exists_by_url(self, url: str) -> bool:
        """
        检查 URL 对应的文章是否存在

        Args:
            url: 文章 URL

        Returns:
            文章是否存在
        """
        url_hash = self._generate_url_hash(url)
        return await self.exists(
            self.TABLE_NAME, "url_hash = :url_hash", {"url_hash": url_hash}
        )

    async def update_status(
        self, article_id: int, status: PendingArticleStatus
    ) -> int:
        """
        更新文章状态

        Args:
            article_id: 文章 ID
            status: 新状态

        Returns:
            影响的行数
        """
        data = {
            "status": status.value,
            "updated_at": datetime.now(),
        }

        return await self.update(
            self.TABLE_NAME, data, "id = :id", {"id": article_id}
        )

    async def delete_by_id(self, article_id: int) -> int:
        """
        删除待爬文章

        Args:
            article_id: 文章 ID

        Returns:
            影响的行数
        """
        return await super().delete(self.TABLE_NAME, "id = :id", {"id": article_id})

    async def count_by_source(self, source_id: int) -> int:
        """
        统计指定源的待爬文章数量

        Args:
            source_id: 源 ID

        Returns:
            文章数量
        """
        return await self.count(
            self.TABLE_NAME, "source_id = :source_id", {"source_id": source_id}
        )

    async def count_by_status(
        self, source_id: int | None = None, status: PendingArticleStatus | None = None
    ) -> int:
        """
        统计指定状态的文章数量（自动过滤低质量文章）

        Args:
            source_id: 源 ID（可选）
            status: 文章状态（可选）

        Returns:
            文章数量
        """
        where_clauses = ["status != 'low_quality'"]
        params = {}

        if source_id is not None:
            where_clauses.append("source_id = :source_id")
            params["source_id"] = source_id

        if status is not None:
            where_clauses.append("status = :status")
            params["status"] = status.value

        where_clause = " AND ".join(where_clauses)

        return await self.count(self.TABLE_NAME, where_clause, params)
