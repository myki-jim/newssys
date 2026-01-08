"""
用户 Repository
处理用户数据的持久化操作
"""

from typing import Any, Dict, List, Optional

from src.core.orm_models import UserRole
from src.repository.base import BaseRepository


class UserRepository(BaseRepository):
    """用户数据访问层"""

    TABLE_NAME = "users"

    def __init__(self, session):
        super().__init__(session)

    async def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名获取用户"""
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE username = :username"
        return await self.fetch_one(sql, {"username": username})

    async def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取用户"""
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE id = :id"
        return await self.fetch_one(sql, {"id": user_id})

    async def list(
        self,
        role: Optional[UserRole] = None,
        is_active: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """获取用户列表"""
        conditions = []
        params = {"limit": limit, "offset": offset}

        if role:
            conditions.append("role = :role")
            params["role"] = role.value

        if is_active is not None:
            conditions.append("is_active = :is_active")
            params["is_active"] = is_active

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        sql = f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """

        return await self.fetch_all(sql, params)

    async def create(self, user: Dict[str, Any]) -> int:
        """创建用户"""
        data = {
            "username": user["username"],
            "password": user["password"],
            "role": user.get("role", "user"),
            "is_active": user.get("is_active", True),
            "office": user.get("office"),
        }
        return await self.insert(self.TABLE_NAME, data, returning="id")

    async def update(self, user_id: int, data: Dict[str, Any]) -> bool:
        """更新用户"""
        update_data = {k: v for k, v in data.items() if v is not None}
        if not update_data:
            return False

        # 处理 role 枚举
        if "role" in update_data:
            if isinstance(update_data["role"], UserRole):
                update_data["role"] = update_data["role"].value

        set_clause = ", ".join(f"{k} = :{k}" for k in update_data.keys())
        update_data["id"] = user_id
        sql = f"UPDATE {self.TABLE_NAME} SET {set_clause} WHERE id = :id"

        return await self.execute_write(sql, update_data) > 0

    async def delete(self, user_id: int) -> bool:
        """删除用户"""
        return await super().delete(self.TABLE_NAME, "id = :id", {"id": user_id})

    async def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """验证用户登录"""
        user = await self.get_by_username(username)
        if not user:
            return None
        if not user.get("is_active"):
            return None
        if user.get("password") != password:  # 明文密码比较
            return None
        return user
