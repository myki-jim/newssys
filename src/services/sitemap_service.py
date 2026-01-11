"""
Sitemap 服务
处理 robots.txt 解析和 Sitemap 递归获取
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import (
    PendingArticleCreate,
    Sitemap,
    SitemapCreate,
    SitemapFetchStatus,
)
from src.repository.pending_article_repository import PendingArticleRepository
from src.repository.sitemap_repository import SitemapRepository
from src.repository.source_repository import SourceRepository


logger = logging.getLogger(__name__)


class SitemapService:
    """
    Sitemap 服务
    负责：
    1. 解析 robots.txt 获取 Sitemap
    2. 递归解析 Sitemap 索引（获取叶子节点）
    3. 从 Sitemap 提取文章链接
    """

    def __init__(self, session: AsyncSession) -> None:
        """初始化 SitemapService"""
        self.session = session
        self.sitemap_repo = SitemapRepository(session)
        self.pending_repo = PendingArticleRepository(session)
        self.source_repo = SourceRepository(session)

        # HTTP 客户端配置（使用浏览器 User-Agent 避免 403）
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            },
            follow_redirects=True,
        )

    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        await self.client.aclose()

    async def fetch_robots_sitemaps(self, source_id: int) -> list[Sitemap]:
        """
        从 robots.txt 获取 Sitemap 列表

        Args:
            source_id: 源 ID

        Returns:
            解析到的 Sitemap 列表
        """
        # 获取源信息
        source = await self.source_repo.fetch_by_id(source_id)
        if not source:
            logger.error(f"Source {source_id} not found")
            return []

        base_url = source["base_url"]
        parsed_url = urlparse(base_url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"

        logger.info(f"Fetching robots.txt for source {source_id}: {robots_url}")

        try:
            response = await self.client.get(robots_url)
            response.raise_for_status()

            robots_content = response.text
            sitemaps = self._parse_sitemaps_from_robots(robots_content, base_url)

            # 存储到数据库
            result = []
            for sitemap_url in sitemaps:
                # 检查是否已存在
                existing = await self.sitemap_repo.get_by_url(sitemap_url)
                if not existing:
                    sitemap_id = await self.sitemap_repo.create(
                        SitemapCreate(source_id=source_id, url=sitemap_url)
                    )
                    result.append(Sitemap(id=sitemap_id, source_id=source_id, url=sitemap_url))
                    logger.info(f"Created sitemap {sitemap_id}: {sitemap_url}")
                else:
                    result.append(Sitemap(**existing))
                    logger.info(f"Sitemap already exists: {sitemap_url}")

            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch robots.txt for {robots_url}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing robots.txt for {robots_url}: {e}")
            return []

    def _parse_sitemaps_from_robots(self, content: str, base_url: str) -> list[str]:
        """
        从 robots.txt 内容解析 Sitemap URL

        Args:
            content: robots.txt 内容
            base_url: 基础 URL

        Returns:
            Sitemap URL 列表
        """
        sitemaps = []
        for line in content.splitlines():
            line = line.strip()
            if line.lower().startswith("sitemap:"):
                sitemap_url = line.split(":", 1)[1].strip()
                # 转换为绝对 URL
                if not sitemap_url.startswith("http"):
                    sitemap_url = urljoin(base_url, sitemap_url)
                sitemaps.append(sitemap_url)

        logger.info(f"Found {len(sitemaps)} sitemap(s) in robots.txt")
        return sitemaps

    async def fetch_and_parse_sitemap(
        self, sitemap_id: int, recursive: bool = True
    ) -> dict[str, Any]:
        """
        获取并解析 Sitemap（递归解析索引）

        Args:
            sitemap_id: Sitemap ID
            recursive: 是否递归解析子 Sitemap

        Returns:
            解析结果：{"leaf_sitemaps": [], "articles": []}
        """
        sitemap = await self.sitemap_repo.get_by_id(sitemap_id)
        if not sitemap:
            logger.error(f"Sitemap {sitemap_id} not found")
            return {"leaf_sitemaps": [], "articles": []}

        sitemap_url = sitemap["url"]
        logger.info(f"Fetching sitemap {sitemap_id}: {sitemap_url}")

        try:
            response = await self.client.get(sitemap_url)
            response.raise_for_status()

            content = response.text

            # 判断是 Sitemap 索引还是普通 Sitemap
            if "<sitemapindex" in content:
                logger.info(f"Sitemap {sitemap_url} is an index, parsing recursively...")
                result = await self._parse_sitemap_index(
                    content, sitemap["source_id"], sitemap_url, recursive
                )
            else:
                logger.info(f"Sitemap {sitemap_url} is a leaf sitemap, parsing articles...")
                articles = await self._parse_sitemap_articles(content, sitemap["source_id"], sitemap_id)
                result = {"leaf_sitemaps": [sitemap_id], "articles": articles}

            # 更新 Sitemap 状态
            from src.core.models import SitemapUpdate
            await self.sitemap_repo.update_by_id(
                sitemap_id,
                SitemapUpdate(fetch_status=SitemapFetchStatus.SUCCESS)
            )
            await self.sitemap_repo.update_last_fetched(sitemap_id)

            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch sitemap {sitemap_url}: {e}")
            from src.core.models import SitemapUpdate
            await self.sitemap_repo.update_by_id(sitemap_id, SitemapUpdate(fetch_status=SitemapFetchStatus.SUCCESS))
            return {"leaf_sitemaps": [], "articles": []}
        except Exception as e:
            logger.error(f"Error parsing sitemap {sitemap_url}: {e}")
            from src.core.models import SitemapUpdate
            await self.sitemap_repo.update_by_id(sitemap_id, SitemapUpdate(fetch_status=SitemapFetchStatus.SUCCESS))
            return {"leaf_sitemaps": [], "articles": []}

    async def _parse_sitemap_index(
        self, content: str, source_id: int, base_url: str, recursive: bool
    ) -> dict[str, Any]:
        """
        解析 Sitemap 索引（递归）

        Args:
            content: Sitemap XML 内容
            source_id: 源 ID
            base_url: 基础 URL
            recursive: 是否递归解析

        Returns:
            解析结果
        """
        soup = BeautifulSoup(content, "xml")
        sitemap_tags = soup.find_all("sitemap")

        leaf_sitemaps = []
        all_articles = []

        for tag in sitemap_tags:
            loc_tag = tag.find("loc")
            if not loc_tag:
                continue

            sub_sitemap_url = loc_tag.text.strip()

            if recursive:
                # 递归解析子 Sitemap
                logger.info(f"Recursively parsing sub-sitemap: {sub_sitemap_url}")

                # 检查是否已存在
                existing = await self.sitemap_repo.get_by_url(sub_sitemap_url)
                if existing:
                    sub_sitemap_id = existing["id"]
                else:
                    # 创建子 Sitemap 记录
                    sub_sitemap_id = await self.sitemap_repo.create(
                        SitemapCreate(source_id=source_id, url=sub_sitemap_url)
                    )

                # 递归解析
                result = await self.fetch_and_parse_sitemap(sub_sitemap_id, recursive=True)
                leaf_sitemaps.extend(result.get("leaf_sitemaps", []))
                all_articles.extend(result.get("articles", []))
            else:
                # 不递归，直接记录为叶子节点
                existing = await self.sitemap_repo.get_by_url(sub_sitemap_url)
                if existing:
                    leaf_sitemaps.append(existing["id"])
                else:
                    sitemap_id = await self.sitemap_repo.create(
                        SitemapCreate(source_id=source_id, url=sub_sitemap_url)
                    )
                    leaf_sitemaps.append(sitemap_id)

        return {"leaf_sitemaps": leaf_sitemaps, "articles": all_articles}

    async def _parse_sitemap_articles(
        self, content: str, source_id: int, sitemap_id: int
    ) -> list[PendingArticleCreate]:
        """
        解析 Sitemap 中的文章链接

        只保留最近30天的文章

        Args:
            content: Sitemap XML 内容
            source_id: 源 ID
            sitemap_id: Sitemap ID

        Returns:
            待爬文章列表
        """
        soup = BeautifulSoup(content, "xml")
        url_tags = soup.find_all("url")

        articles = []
        # 30天前的时间（使用 UTC 时区以匹配解析后的时区感知时间）
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
        filtered_count = 0

        for tag in url_tags:
            loc_tag = tag.find("loc")
            if not loc_tag:
                continue

            url = loc_tag.text.strip()

            # 提取可选字段
            title = None
            title_tag = tag.find("title")
            if title_tag and title_tag.text:
                title = title_tag.text.strip()

            # 解析发布时间
            publish_time = None
            time_tags = tag.find_all(["lastmod", "pubdate", "publication_date"])
            for time_tag in time_tags:
                if time_tag and time_tag.text:
                    try:
                        # 尝试解析 ISO 格式时间
                        time_str = time_tag.text.strip()
                        # 处理各种 ISO 格式
                        time_str = time_str.replace("Z", "+00:00")
                        parsed_time = datetime.fromisoformat(time_str)

                        # 如果解析出的时间没有时区信息，添加 UTC 时区
                        if parsed_time.tzinfo is None:
                            parsed_time = parsed_time.replace(tzinfo=timezone.utc)

                        # 只保留最近30天的文章
                        if parsed_time < cutoff_date:
                            filtered_count += 1
                            continue

                        publish_time = parsed_time
                        break
                    except (ValueError, AttributeError):
                        continue

            # 如果没有时间信息，默认保留（无法判断是否过期）
            # 如果有时间但超过30天，已在上面跳过

            articles.append(
                PendingArticleCreate(
                    source_id=source_id,
                    sitemap_id=sitemap_id,
                    url=url,
                    title=title,
                    publish_time=publish_time,
                )
            )

        logger.info(f"Parsed {len(articles)} articles from sitemap {sitemap_id} (filtered {filtered_count} older than 30 days)")
        return articles

    async def import_articles_to_pending(
        self, articles: list[PendingArticleCreate]
    ) -> dict[str, int]:
        """
        导入文章到待爬表

        Args:
            articles: 待爬文章列表

        Returns:
            导入统计：{"created": 数量, "existing": 数量}
        """
        created = 0
        existing = 0

        for article in articles:
            # 检查 URL 是否已存在
            if await self.pending_repo.exists_by_url(article.url):
                existing += 1
            else:
                await self.pending_repo.create(article)
                created += 1

        logger.info(f"Imported articles: {created} new, {existing} existing")
        return {"created": created, "existing": existing}

    async def sync_source_sitemaps(self, source_id: int) -> dict[str, Any]:
        """
        同步源的所有 Sitemap 和文章

        完整流程：
        1. 从 robots.txt 获取 Sitemap
        2. 递归解析所有 Sitemap
        3. 提取文章链接到待爬表

        Args:
            source_id: 源 ID

        Returns:
            同步结果统计
        """
        logger.info(f"Starting sitemap sync for source {source_id}")

        # 1. 从 robots.txt 获取 Sitemap
        sitemaps = await self.fetch_robots_sitemaps(source_id)
        if not sitemaps:
            logger.warning(f"No sitemaps found for source {source_id}")
            return {
                "sitemaps_found": 0,
                "articles_imported": 0,
                "error": "No sitemaps found",
            }

        # 2. 递归解析所有 Sitemap
        all_articles = []
        for sitemap in sitemaps:
            result = await self.fetch_and_parse_sitemap(sitemap.id, recursive=True)
            all_articles.extend(result.get("articles", []))

        # 3. 导入到待爬表
        import_result = await self.import_articles_to_pending(all_articles)

        logger.info(
            f"Sitemap sync complete for source {source_id}: "
            f"{len(sitemaps)} sitemaps, {import_result['created']} new articles"
        )

        return {
            "sitemaps_found": len(sitemaps),
            "articles_imported": import_result["created"],
            "articles_existing": import_result["existing"],
        }

    async def add_custom_sitemap(
        self, source_id: int | None, sitemap_url: str
    ) -> dict[str, Any]:
        """
        手动添加 Sitemap

        如果指定 source_id，添加到该源
        如果不指定 source_id，尝试从 URL 匹配现有源或创建新源

        Args:
            source_id: 源 ID（可选）
            sitemap_url: Sitemap URL

        Returns:
            创建的 Sitemap 信息
        """
        # 确定 source_id
        target_source_id = source_id

        if target_source_id is None:
            # 从 URL 提取域名，尝试匹配现有源
            parsed_url = urlparse(sitemap_url)
            domain = f"{parsed_url.scheme}://{parsed_url.netloc}"

            # 查找匹配的源
            sources = await self.source_repo.fetch_all(
                "SELECT * FROM crawl_sources ORDER BY created_at DESC LIMIT 100"
            )
            for source in sources:
                if domain in source["base_url"] or source["base_url"] in domain:
                    target_source_id = source["id"]
                    logger.info(f"Matched sitemap to existing source {target_source_id}")
                    break

            if target_source_id is None:
                # 创建新源
                from src.core.models import ParserConfig, SourceCreate
                new_source_id = await self.source_repo.create(
                    SourceCreate(
                        site_name=f"Auto-generated from {parsed_url.netloc}",
                        base_url=domain,
                        parser_config=ParserConfig(
                            title_selector="h1",
                            content_selector="article, main",
                        ),
                        enabled=True,  # 添加 sitemap 时自动启用源
                    )
                )
                target_source_id = new_source_id
                logger.info(f"Created new source {target_source_id} for sitemap")

        # 检查 Sitemap 是否已存在
        existing = await self.sitemap_repo.get_by_url(sitemap_url)
        if existing:
            return {
                "sitemap_id": existing["id"],
                "source_id": existing["source_id"],
                "url": existing["url"],
                "status": "existing",
            }

        # 创建 Sitemap
        sitemap_id = await self.sitemap_repo.create(
            SitemapCreate(source_id=target_source_id, url=sitemap_url)
        )

        return {
            "sitemap_id": sitemap_id,
            "source_id": target_source_id,
            "url": sitemap_url,
            "status": "created",
        }
