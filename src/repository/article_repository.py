"""
文章 Repository 模块
负责文章数据的持久化操作
"""

import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Article, ArticleCreate, ArticleStatus, ArticleUpdate, FetchStatus
from src.repository.base import BaseRepository


class ArticleRepository(BaseRepository):
    """
    文章数据访问层
    处理文章的存储、查询、更新和去重
    """

    TABLE_NAME = "articles"

    def __init__(self, session: AsyncSession | None = None) -> None:
        """初始化 ArticleRepository"""
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

    async def create(self, article: ArticleCreate) -> int | None:
        """
        创建新文章

        Args:
            article: 文章创建数据

        Returns:
            新插入文章的 ID
        """
        url_hash = self._generate_url_hash(article.url)

        data = {
            "url_hash": url_hash,
            "url": article.url,
            "title": article.title,
            "content": article.content,
            "publish_time": article.publish_time,
            "author": article.author,
            "source_id": article.source_id,
            "status": ArticleStatus.RAW.value,
            "fetch_status": FetchStatus.SUCCESS.value,
            "retry_count": 0,
            "crawled_at": datetime.now(),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        return await self.insert(self.TABLE_NAME, data, returning="id")

    async def create_from_scraped(self, scraped_article: Any, source_id: int) -> int | None:
        """
        从爬取的文章对象创建文章记录

        Args:
            scraped_article: 爬取的文章对象（有 title, content, publish_time, author, url 属性）
            source_id: 源 ID

        Returns:
            新插入文章的 ID
        """
        url_hash = self._generate_url_hash(scraped_article.url)

        data = {
            "url_hash": url_hash,
            "url": scraped_article.url,
            "title": scraped_article.title or "无标题",
            "content": scraped_article.content,
            "publish_time": scraped_article.publish_time,
            "author": scraped_article.author,
            "source_id": source_id,
            "status": ArticleStatus.RAW.value,
            "fetch_status": FetchStatus.SUCCESS.value,
            "retry_count": 0,
            "crawled_at": datetime.now(),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        return await self.insert(self.TABLE_NAME, data, returning="id")

    async def get_by_id(self, article_id: int) -> dict[str, Any] | None:
        """
        根据 ID 获取文章

        Args:
            article_id: 文章 ID

        Returns:
            文章数据字典，不存在时返回 None
        """
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE id = :id"
        return await self.fetch_one(sql, {"id": article_id})

    # 别名方法，与 API 调用保持一致
    async def fetch_by_id(self, article_id: int) -> dict[str, Any] | None:
        """获取文章详情（别名方法）"""
        return await self.get_by_id(article_id)

    async def get_by_url_hash(self, url_hash: str) -> dict[str, Any] | None:
        """
        根据 URL 哈希获取文章

        Args:
            url_hash: URL 哈希值

        Returns:
            文章数据字典，不存在时返回 None
        """
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE url_hash = :url_hash"
        return await self.fetch_one(sql, {"url_hash": url_hash})

    # 别名方法
    async def fetch_by_url_hash(self, url_hash: str) -> dict[str, Any] | None:
        """根据 URL 哈希获取文章（别名方法）"""
        return await self.get_by_url_hash(url_hash)

    async def get_by_url(self, url: str) -> dict[str, Any] | None:
        """
        根据 URL 获取文章

        Args:
            url: 文章 URL

        Returns:
            文章数据字典，不存在时返回 None
        """
        url_hash = self._generate_url_hash(url)
        return await self.get_by_url_hash(url_hash)

    async def exists_by_url(self, url: str) -> bool:
        """
        检查 URL 对应的文章是否存在

        Args:
            url: 文章 URL

        Returns:
            文章是否存在
        """
        url_hash = self._generate_url_hash(url)
        return await self.exists(self.TABLE_NAME, "url_hash = :url_hash", {"url_hash": url_hash})

    async def update_by_id(
        self, article_id: int, update: ArticleUpdate
    ) -> int:
        """
        更新文章信息

        Args:
            article_id: 文章 ID
            update: 更新数据

        Returns:
            影响的行数
        """
        data: dict[str, Any] = {"updated_at": datetime.now()}

        if update.title is not None:
            data["title"] = update.title
        if update.content is not None:
            data["content"] = update.content
        if update.publish_time is not None:
            data["publish_time"] = update.publish_time
        if update.author is not None:
            data["author"] = update.author
        if update.status is not None:
            data["status"] = update.status.value
            # 根据状态更新对应的时间戳
            if update.status == ArticleStatus.PROCESSED:
                data["processed_at"] = datetime.now()
            elif update.status == ArticleStatus.SYNCED:
                data["synced_at"] = datetime.now()
        if update.error_message is not None:
            data["error_message"] = update.error_message

        return await self.update(
            self.TABLE_NAME, data, "id = :id", {"id": article_id}
        )

    async def update_status(
        self, article_id: int, status: ArticleStatus, error_message: str | None = None
    ) -> int:
        """
        更新文章状态

        Args:
            article_id: 文章 ID
            status: 新状态
            error_message: 错误信息（可选）

        Returns:
            影响的行数
        """
        data: dict[str, Any] = {
            "status": status.value,
            "updated_at": datetime.now(),
        }

        if status == ArticleStatus.PROCESSED:
            data["processed_at"] = datetime.now()
        elif status == ArticleStatus.SYNCED:
            data["synced_at"] = datetime.now()

        if error_message is not None:
            data["error_message"] = error_message

        # 使用 BaseRepository 的 update 方法
        return await super().update(
            self.TABLE_NAME, data, "id = :id", {"id": article_id}
        )

    async def delete_by_id(self, article_id: int) -> int:
        """
        删除文章

        Args:
            article_id: 文章 ID

        Returns:
            影响的行数
        """
        return await super().delete(self.TABLE_NAME, "id = :id", {"id": article_id})

    async def update(self, article_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """
        更新文章（通用方法）

        Args:
            article_id: 文章 ID
            data: 更新数据字典

        Returns:
            更新后的文章数据
        """
        update_data: dict[str, Any] = {"updated_at": datetime.now()}

        # 处理各种字段
        if "title" in data and data["title"] is not None:
            update_data["title"] = data["title"]
        if "content" in data and data["content"] is not None:
            update_data["content"] = data["content"]
            # 更新内容哈希
            from src.services.simhash import compute_content_hash
            update_data["content_hash"] = compute_content_hash(data["content"])
        if "publish_time" in data and data["publish_time"] is not None:
            update_data["publish_time"] = data["publish_time"]
        if "author" in data and data["author"] is not None:
            update_data["author"] = data["author"]
        if "status" in data and data["status"] is not None:
            if hasattr(data["status"], "value"):
                update_data["status"] = data["status"].value
            else:
                update_data["status"] = data["status"]
        if "fetch_status" in data and data["fetch_status"] is not None:
            if hasattr(data["fetch_status"], "value"):
                update_data["fetch_status"] = data["fetch_status"].value
            else:
                update_data["fetch_status"] = data["fetch_status"]
        if "error_msg" in data and data["error_msg"] is not None:
            update_data["error_msg"] = data["error_msg"]

        # 执行更新
        set_clauses = [f"{k} = :_{k}" for k in update_data.keys()]
        placeholders = {f"_{k}": v for k, v in update_data.items()}
        placeholders["_id"] = article_id

        sql = f"""
            UPDATE {self.TABLE_NAME}
            SET {', '.join(set_clauses)}
            WHERE id = :_id
            RETURNING *
        """

        result = await self.fetch_one(sql, placeholders)
        # 重要：UPDATE 语句需要显式提交事务
        await self.session.commit()
        return dict(result) if result else await self.fetch_by_id(article_id)  # type: ignore

    async def delete(self, article_id: int) -> bool:
        """
        删除文章（API 调用方法）

        Args:
            article_id: 文章 ID

        Returns:
            是否成功删除
        """
        rows = await self.delete_by_id(article_id)
        return rows > 0

    async def list_by_source(
        self,
        source_id: int,
        status: ArticleStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        根据源 ID 列出文章

        Args:
            source_id: 源 ID
            status: 文章状态（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            文章列表
        """
        params: dict[str, Any] = {"source_id": source_id, "limit": limit, "offset": offset}
        where_clause = "source_id = :source_id"

        if status is not None:
            where_clause += " AND status = :status"
            params["status"] = status.value

        sql = f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """

        return await self.fetch_all(sql, params)

    async def list_by_status(
        self,
        status: ArticleStatus,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """
        根据状态列出文章

        Args:
            status: 文章状态
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            文章列表
        """
        sql = f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE status = :status
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """

        return await self.fetch_all(sql, {"status": status.value, "limit": limit, "offset": offset})

    async def count_by_source(self, source_id: int) -> int:
        """
        统计指定源的文章数量

        Args:
            source_id: 源 ID

        Returns:
            文章数量
        """
        return await self.count(self.TABLE_NAME, "source_id = :source_id", {"source_id": source_id})

    async def count_by_status(self, status: ArticleStatus) -> int:
        """
        统计指定状态的文章数量

        Args:
            status: 文章状态

        Returns:
            文章数量
        """
        return await self.count(self.TABLE_NAME, "status = :status", {"status": status.value})

    async def get_latest_articles(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        获取最新的文章

        Args:
            limit: 返回数量限制

        Returns:
            文章列表
        """
        sql = f"""
            SELECT * FROM {self.TABLE_NAME}
            ORDER BY created_at DESC
            LIMIT :limit
        """

        return await self.fetch_all(sql, {"limit": limit})

    async def batch_create(self, articles: list[ArticleCreate]) -> int:
        """
        批量创建文章

        Args:
            articles: 文章创建数据列表

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
                "url_hash": url_hash,
                "url": article.url,
                "title": article.title,
                "content": article.content,
                "publish_time": article.publish_time,
                "author": article.author,
                "source_id": article.source_id,
                "status": ArticleStatus.RAW.value,
                "crawled_at": now,
                "created_at": now,
                "updated_at": now,
            })

        return await self.insert_many(self.TABLE_NAME, data_list)

    async def search_articles(
        self,
        keywords: list[str],
        limit: int = 10,
        days_ago: int = 30,
    ) -> list[dict[str, Any]]:
        """
        搜索文章（用于AI Agent内部知识库搜索）- 使用模糊匹配

        Args:
            keywords: 关键词列表
            limit: 返回数量限制
            days_ago: 搜索最近N天的文章

        Returns:
            匹配的文章列表，按时间倒序
        """
        from datetime import timedelta

        if not keywords:
            # 如果没有关键词，返回最近的文章
            cutoff_date = datetime.now() - timedelta(days=days_ago)
            sql = f"""
                SELECT id, url, title, content, publish_time, author, source_id, created_at
                FROM {self.TABLE_NAME}
                WHERE publish_time >= :cutoff_date
                ORDER BY publish_time DESC, created_at DESC
                LIMIT :limit
            """
            results = await self.fetch_all(sql, {"cutoff_date": cutoff_date, "limit": limit})
        else:
            # 构建模糊匹配查询 - 每个关键词分别匹配
            conditions = []
            params = {"limit": limit * 2}  # 获取更多结果用于去重

            # 为每个关键词创建多个匹配条件（标题、内容）
            for i, keyword in enumerate(keywords):
                # 原始关键词
                param_full = f"kw_{i}_full"
                # 关键词分词后的每个词
                words = [w for w in keyword.split() if len(w) > 1]

                keyword_ors = []
                # 完整关键词匹配标题
                keyword_ors.append(f"title LIKE :{param_full}")
                params[param_full] = f"%{keyword}%"

                # 完整关键词匹配内容
                param_content = f"kw_{i}_content"
                keyword_ors.append(f"content LIKE :{param_content}")
                params[param_content] = f"%{keyword}%"

                # 分词后的每个词也匹配
                for j, word in enumerate(words):
                    param_word = f"kw_{i}_w_{j}"
                    keyword_ors.append(f"title LIKE :{param_word}")
                    params[param_word] = f"%{word}%"

                conditions.append(f"({' OR '.join(keyword_ors)})")

            # 构建 SQL
            where_clause = " OR ".join(conditions)
            sql = f"""
                SELECT DISTINCT id, url, title, content, publish_time, author, source_id, created_at
                FROM {self.TABLE_NAME}
                WHERE {where_clause}
                ORDER BY publish_time DESC, created_at DESC
                LIMIT :limit
            """

            results = await self.fetch_all(sql, params)

        # 如果结果不足，扩大搜索范围（不限制时间）
        if len(results) < limit and keywords:
            conditions = []
            params = {"limit": limit - len(results)}

            for i, keyword in enumerate(keywords):
                param_full = f"kw2_{i}_full"
                conditions.append(f"title LIKE :{param_full}")
                params[param_full] = f"%{keyword}%"

            where_clause = " OR ".join(conditions)
            sql = f"""
                SELECT DISTINCT id, url, title, content, publish_time, author, source_id, created_at
                FROM {self.TABLE_NAME}
                WHERE {where_clause}
                ORDER BY publish_time DESC, created_at DESC
                LIMIT :limit
            """

            additional_results = await self.fetch_all(sql, params)
            # 合并结果（去重）
            seen_ids = {r["id"] for r in results}
            for r in additional_results:
                if r["id"] not in seen_ids:
                    results.append(r)
                    seen_ids.add(r["id"])

        # 格式化结果
        formatted_results = []
        for row in results[:limit]:
            source_name = await self._get_source_name(row["source_id"])

            # publish_time 可能是 datetime 对象或字符串
            publish_time = row["publish_time"]
            if publish_time and hasattr(publish_time, "isoformat"):
                publish_time = publish_time.isoformat()

            formatted_results.append({
                "title": row["title"],
                "url": row["url"],
                "publish_time": publish_time,
                "content": row["content"][:500] + "..." if row["content"] and len(row["content"]) > 500 else row["content"],
                "author": row["author"],
                "source": source_name,
            })

        return formatted_results

    async def _get_source_name(self, source_id: int) -> str:
        """获取源名称"""
        sql = "SELECT site_name FROM crawl_sources WHERE id = :source_id"
        result = await self.fetch_one(sql, {"source_id": source_id})
        return result["site_name"] if result else "未知来源"

    async def fetch_by_timerange(
        self,
        start_date,
        end_date,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        根据时间范围获取文章

        Args:
            start_date: 开始时间
            end_date: 结束时间
            language: 语言筛选（可选）

        Returns:
            文章列表
        """
        params = {"start_date": start_date, "end_date": end_date}

        # 构建SQL
        where_clause = "publish_time >= :start_date AND publish_time <= :end_date"

        # 如果需要语言筛选（可以根据源或其他字段判断）
        # 这里暂时不实现语言筛选，因为 articles 表没有 language 字段

        sql = f"""
            SELECT id, url, title, content, publish_time, author, source_id, created_at
            FROM {self.TABLE_NAME}
            WHERE {where_clause}
            ORDER BY publish_time DESC
        """

        results = await self.fetch_all(sql, params)
        return results
