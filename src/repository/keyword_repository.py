"""
搜索关键词 Repository
"""

from datetime import datetime
from typing import Any, Dict, List

from src.repository.base import BaseRepository


class KeywordRepository(BaseRepository):
    """搜索关键词仓库"""

    async def create(self, keyword: Dict[str, Any]) -> int:
        """创建关键词"""
        return await self.insert(
            "search_keywords",
            {
                "keyword": keyword["keyword"],
                "description": keyword.get("description"),
                "time_range": keyword.get("time_range", "w"),
                "max_results": keyword.get("max_results", 10),
                "region": keyword.get("region", "us-en"),
                "is_active": keyword.get("is_active", True),
            },
            returning="id",
        )

    async def get_by_id(self, keyword_id: int) -> Dict[str, Any] | None:
        """根据ID获取关键词"""
        result = await self.fetch_one(
            "SELECT * FROM search_keywords WHERE id = :id", {"id": keyword_id}
        )
        return dict(result) if result else None

    async def list(
        self,
        is_active: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """获取关键词列表"""
        if is_active is not None:
            sql = """
                SELECT * FROM search_keywords
                WHERE is_active = :is_active
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """
            return await self.fetch_all(
                sql, {"is_active": is_active, "limit": limit, "offset": offset}
            )

        sql = """
            SELECT * FROM search_keywords
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """
        return await self.fetch_all(sql, {"limit": limit, "offset": offset})

    async def update(self, keyword_id: int, data: dict[str, Any]) -> bool:
        """更新关键词"""
        if not data:
            return False

        set_clause = ", ".join(f"{k} = :{k}" for k in data.keys())
        data["id"] = keyword_id
        sql = f"UPDATE search_keywords SET {set_clause} WHERE id = :id"

        result = await self.execute_write(sql, data)
        return result > 0

    async def delete(self, keyword_id: int) -> bool:
        """删除关键词"""
        result = await self.execute_write(
            "DELETE FROM search_keywords WHERE id = :id", {"id": keyword_id}
        )
        return result > 0

    async def increment_search_count(self, keyword_id: int) -> bool:
        """增加搜索次数"""
        now = datetime.now().isoformat()
        sql = """
            UPDATE search_keywords
            SET search_count = search_count + 1,
                last_searched_at = :now
            WHERE id = :id
        """
        return await self.execute_write(sql, {"now": now, "id": keyword_id}) > 0

    async def get_active_keywords(self) -> List[Dict[str, Any]]:
        """获取所有活跃的关键词"""
        sql = """
            SELECT * FROM search_keywords
            WHERE is_active = 1
            ORDER BY created_at ASC
        """
        return await self.fetch_all(sql, {})
