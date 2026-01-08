"""
搜索关键词管理 API
提供关键词的增删改查功能
"""

from typing import List

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import (
    APIResponse,
    KeywordCreate,
    KeywordResponse,
    KeywordUpdate,
)
from src.core.database import get_async_session
from src.core.models import SourceCreate
from src.repository.article_repository import ArticleRepository
from src.repository.keyword_repository import KeywordRepository
from src.repository.source_repository import SourceRepository

router = APIRouter(prefix="/keywords", tags=["关键词管理"])


@router.get("", response_model=APIResponse[List[KeywordResponse]])
async def list_keywords(
    is_active: bool | None = Query(None, description="是否只显示激活的关键词"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """获取关键词列表"""
    async with get_async_session() as db:
        repo = KeywordRepository(db)
        keywords = await repo.list(is_active=is_active, limit=limit, offset=offset)
        return APIResponse(success=True, data=keywords)


@router.get("/{keyword_id}", response_model=APIResponse[KeywordResponse])
async def get_keyword(keyword_id: int):
    """获取单个关键词"""
    async with get_async_session() as db:
        repo = KeywordRepository(db)
        keyword = await repo.get_by_id(keyword_id)
        if not keyword:
            raise HTTPException(status_code=404, detail="关键词不存在")
        return APIResponse(success=True, data=keyword)


@router.post("", response_model=APIResponse[KeywordResponse])
async def create_keyword(keyword: KeywordCreate):
    """创建关键词"""
    async with get_async_session() as db:
        repo = KeywordRepository(db)
        keyword_id = await repo.create(keyword.model_dump())
        created = await repo.get_by_id(keyword_id)
        return APIResponse(success=True, data=created)


@router.put("/{keyword_id}", response_model=APIResponse[KeywordResponse])
async def update_keyword(keyword_id: int, keyword: KeywordUpdate):
    """更新关键词"""
    async with get_async_session() as db:
        repo = KeywordRepository(db)

        existing = await repo.get_by_id(keyword_id)
        if not existing:
            raise HTTPException(status_code=404, detail="关键词不存在")

        update_data = keyword.model_dump(exclude_unset=True)
        await repo.update(keyword_id, update_data)
        updated = await repo.get_by_id(keyword_id)

        return APIResponse(success=True, data=updated)


@router.delete("/{keyword_id}", response_model=APIResponse[dict])
async def delete_keyword(keyword_id: int):
    """删除关键词"""
    async with get_async_session() as db:
        repo = KeywordRepository(db)

        existing = await repo.get_by_id(keyword_id)
        if not existing:
            raise HTTPException(status_code=404, detail="关键词不存在")

        await repo.delete(keyword_id)
        return APIResponse(success=True, data={"message": "删除成功"})


@router.post("/{keyword_id}/search", response_model=APIResponse[dict])
async def search_with_keyword(keyword_id: int):
    """使用关键词执行搜索"""
    import hashlib
    from urllib.parse import urlparse, unquote, parse_qs

    async with get_async_session() as db:
        repo = KeywordRepository(db)

        keyword = await repo.get_by_id(keyword_id)
        if not keyword:
            raise HTTPException(status_code=404, detail="关键词不存在")

        if not keyword["is_active"]:
            raise HTTPException(status_code=400, detail="关键词未激活")

        # 执行搜索
        from src.services.search_engine import WebSearchEngine

        search_engine = WebSearchEngine()
        results = await search_engine.search(
            query=keyword["keyword"],
            time_range=keyword["time_range"],
            max_results=keyword["max_results"],
            region=keyword["region"],
        )

        # 保存搜索结果
        article_repo = ArticleRepository(db)
        source_repo = SourceRepository(db)
        saved_count = 0

        for result in results:
            try:
                # 处理 DDG URL
                url = result.url
                if 'duckduckgo.com/l/' in url and 'uddg=' in url:
                    try:
                        parsed = urlparse(url)
                        params = parse_qs(parsed.query)
                        if 'uddg' in params:
                            url = unquote(params['uddg'][0])
                    except Exception:
                        pass

                # 生成 URL hash 用于去重
                url_hash = hashlib.md5(url.encode()).hexdigest()

                # 检查文章是否已存在
                existing = await article_repo.get_by_url(url)
                if existing:
                    continue

                # 查找或创建来源
                parsed_url = urlparse(url)
                domain = parsed_url.netloc
                base_url_pattern = f"%{domain}%"

                # 直接查询数据库查找相同 domain 的来源（通过 base_url 匹配）
                from sqlalchemy import text

                result = await db.execute(
                    text("SELECT id FROM crawl_sources WHERE base_url LIKE :base_url LIMIT 1"),
                    {"base_url": base_url_pattern}
                )
                source_row = result.fetchone()

                if not source_row:
                    # 没有找到来源，不设置 source_id
                    source_id = None
                else:
                    source_id = source_row[0]

                # 保存文章
                article_data = {
                    "title": result.title or "",
                    "url": url,
                    "url_hash": url_hash,
                    "source_id": source_id,
                    "content": result.body or "",
                    "author": result.author or "",
                    "published_date": result.date or None,
                    "crawl_status": "completed",
                }
                await article_repo.create(article_data)
                saved_count += 1

            except Exception:
                continue

        # 更新搜索次数
        await repo.increment_search_count(keyword_id)

        return APIResponse(
            success=True,
            data={
                "keyword": keyword["keyword"],
                "results_count": len(results),
                "saved_count": saved_count,
                "results": results[:5],  # 返回前5条作为预览
            },
        )


@router.get("/active/list", response_model=APIResponse[List[KeywordResponse]])
async def get_active_keywords():
    """获取所有激活的关键词（用于定时任务）"""
    async with get_async_session() as db:
        repo = KeywordRepository(db)
        keywords = await repo.get_active_keywords()
        return APIResponse(success=True, data=keywords)
