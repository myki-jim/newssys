"""
报告 Repository
负责报告数据的持久化操作
"""

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import (
    Report,
    ReportAgentStage,
    ReportCreate,
    ReportStatus,
    ReportTemplate,
    ReportTemplateCreate,
)
from src.repository.base import BaseRepository


logger = logging.getLogger(__name__)


class ReportRepository(BaseRepository):
    """报告数据访问层"""

    TABLE_NAME = "reports"

    def __init__(self, session: AsyncSession | None = None) -> None:
        super().__init__(session)

    async def create(self, report: ReportCreate) -> dict[str, Any]:
        """创建报告"""
        data = {
            "title": report.title,
            "time_range_start": report.time_range_start,
            "time_range_end": report.time_range_end,
            "template_id": report.template_id,
            "custom_prompt": report.custom_prompt,
            "language": report.language,
            "status": ReportStatus.GENERATING.value,
            "agent_stage": ReportAgentStage.INITIALIZING.value,
            "total_articles": 0,
            "clustered_articles": 0,
            "event_count": 0,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        id = await self.insert(self.TABLE_NAME, data, returning="id")
        # 直接查询并返回，避免递归
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE id = :id"
        result = await self.fetch_one(sql, {"id": id})
        if result:
            result_dict = dict(result)
            if "sections" in result_dict and result_dict["sections"]:
                try:
                    result_dict["sections"] = json.loads(result_dict["sections"])
                except:
                    result_dict["sections"] = []
            return result_dict
        return None

    async def fetch_by_id(self, report_id: int) -> dict[str, Any] | None:
        """根据ID获取报告"""
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE id = :id"
        result = await self.fetch_one(sql, {"id": report_id})

        if result:
            result_dict = dict(result)
            if "sections" in result_dict and result_dict["sections"]:
                try:
                    result_dict["sections"] = json.loads(result_dict["sections"])
                except:
                    result_dict["sections"] = []
            return result_dict

        return None

    async def fetch_all(
        self,
        limit: int = 50,
        offset: int = 0,
        status: ReportStatus | None = None,
    ) -> list[dict[str, Any]]:
        """获取报告列表"""
        params = {"limit": limit, "offset": offset}

        where_clauses = []
        if status:
            where_clauses.append("status = :status")
            params["status"] = status.value

        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
            SELECT * FROM {self.TABLE_NAME}
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """

        # 调用父类的 fetch_all 方法
        results = await super().fetch_all(sql, params)

        # 转换为字典并解析 sections JSON
        processed_results = []
        for result in results:
            result_dict = dict(result)
            if "sections" in result_dict and result_dict["sections"]:
                try:
                    result_dict["sections"] = json.loads(result_dict["sections"])
                except:
                    result_dict["sections"] = []
            processed_results.append(result_dict)

        return processed_results

    async def update(
        self,
        report_id: int,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """更新报告"""
        update_data: dict[str, Any] = {"updated_at": datetime.now()}

        # 处理各种字段
        if "title" in data and data["title"] is not None:
            update_data["title"] = data["title"]
        if "content" in data and data["content"] is not None:
            update_data["content"] = data["content"]
        if "status" in data and data["status"] is not None:
            if hasattr(data["status"], "value"):
                update_data["status"] = data["status"].value
            else:
                update_data["status"] = data["status"]
        if "agent_stage" in data and data["agent_stage"] is not None:
            if hasattr(data["agent_stage"], "value"):
                update_data["agent_stage"] = data["agent_stage"].value
            else:
                update_data["agent_stage"] = data["agent_stage"]
        if "agent_progress" in data:
            update_data["agent_progress"] = data["agent_progress"]
        if "agent_message" in data:
            update_data["agent_message"] = data["agent_message"]
        if "total_articles" in data:
            update_data["total_articles"] = data["total_articles"]
        if "clustered_articles" in data:
            update_data["clustered_articles"] = data["clustered_articles"]
        if "event_count" in data:
            update_data["event_count"] = data["event_count"]
        if "sections" in data:
            update_data["sections"] = json.dumps(data["sections"])
        if "error_message" in data:
            update_data["error_message"] = data["error_message"]

        # 如果状态变为完成，记录完成时间
        if update_data.get("status") == ReportStatus.COMPLETED.value:
            update_data["completed_at"] = datetime.now()

        # 执行更新
        set_clauses = [f"{k} = :_{k}" for k in update_data.keys()]
        placeholders = {f"_{k}": v for k, v in update_data.items()}
        placeholders["_id"] = report_id

        sql = f"""
            UPDATE {self.TABLE_NAME}
            SET {', '.join(set_clauses)}
            WHERE id = :_id
            RETURNING *
        """

        result = await self.fetch_one(sql, placeholders)
        await self.session.commit()

        if result:
            result_dict = dict(result)
            if "sections" in result_dict and result_dict["sections"]:
                try:
                    result_dict["sections"] = json.loads(result_dict["sections"])
                except:
                    result_dict["sections"] = []
            return result_dict

        return None

    async def delete(self, report_id: int) -> bool:
        """删除报告"""
        rows = await super().delete(self.TABLE_NAME, "id = :id", {"id": report_id})
        return rows > 0


class ReportTemplateRepository(BaseRepository):
    """报告模板数据访问层"""

    TABLE_NAME = "report_templates"

    def __init__(self, session: AsyncSession | None = None) -> None:
        super().__init__(session)

    async def create(self, template: ReportTemplateCreate) -> dict[str, Any]:
        """创建模板"""
        data = {
            "name": template.name,
            "description": template.description,
            "system_prompt": template.system_prompt,
            "section_template": json.dumps(template.section_template),
            "is_default": 0,  # 默认不是默认模板
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        id = await self.insert(self.TABLE_NAME, data, returning="id")
        # 直接查询并返回，避免递归
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE id = :id"
        result = await self.fetch_one(sql, {"id": id})
        if result:
            result_dict = dict(result)
            if "section_template" in result_dict and result_dict["section_template"]:
                try:
                    result_dict["section_template"] = json.loads(result_dict["section_template"])
                except:
                    result_dict["section_template"] = []
            return result_dict
        return None

    async def fetch_by_id(self, template_id: int) -> dict[str, Any] | None:
        """根据ID获取模板"""
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE id = :id"
        result = await self.fetch_one(sql, {"id": template_id})

        if result:
            result_dict = dict(result)
            if "section_template" in result_dict and result_dict["section_template"]:
                try:
                    result_dict["section_template"] = json.loads(result_dict["section_template"])
                except:
                    result_dict["section_template"] = []
            return result_dict

        return None

    async def fetch_all(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取所有模板"""
        sql = f"""
            SELECT * FROM {self.TABLE_NAME}
            ORDER BY is_default DESC, created_at DESC
            LIMIT :limit
        """
        # 调用父类的 fetch_all 方法
        results = await super().fetch_all(sql, {"limit": limit})

        # 转换为字典并处理 JSON 字段
        processed_results = []
        for result in results:
            result_dict = dict(result)
            if "section_template" in result_dict and result_dict["section_template"]:
                try:
                    result_dict["section_template"] = json.loads(result_dict["section_template"])
                except:
                    result_dict["section_template"] = []
            processed_results.append(result_dict)

        return processed_results

    async def fetch_default(self) -> dict[str, Any] | None:
        """获取默认模板"""
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE is_default = 1 LIMIT 1"
        result = await self.fetch_one(sql)

        if result:
            result_dict = dict(result)
            if "section_template" in result_dict and result_dict["section_template"]:
                try:
                    result_dict["section_template"] = json.loads(result_dict["section_template"])
                except:
                    result_dict["section_template"] = []
            return result_dict

        return None

    async def update(
        self,
        template_id: int,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """更新模板"""
        update_data: dict[str, Any] = {"updated_at": datetime.now()}

        if "name" in data:
            update_data["name"] = data["name"]
        if "description" in data:
            update_data["description"] = data["description"]
        if "system_prompt" in data:
            update_data["system_prompt"] = data["system_prompt"]
        if "section_template" in data:
            update_data["section_template"] = json.dumps(data["section_template"])

        # 执行更新
        set_clauses = [f"{k} = :_{k}" for k in update_data.keys()]
        placeholders = {f"_{k}": v for k, v in update_data.items()}
        placeholders["_id"] = template_id

        sql = f"""
            UPDATE {self.TABLE_NAME}
            SET {', '.join(set_clauses)}
            WHERE id = :_id
            RETURNING *
        """

        result = await self.fetch_one(sql, placeholders)
        await self.session.commit()

        if result:
            result_dict = dict(result)
            if "section_template" in result_dict and result_dict["section_template"]:
                try:
                    result_dict["section_template"] = json.loads(result_dict["section_template"])
                except:
                    result_dict["section_template"] = []
            return result_dict

        return None

    async def delete(self, template_id: int) -> bool:
        """删除模板"""
        rows = await super().delete(self.TABLE_NAME, "id = :id", {"id": template_id})
        return rows > 0
