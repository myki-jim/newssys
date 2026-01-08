"""
站点发现器
整合 Robots 处理器和 Sitemap 解析器，提供自动发现能力
"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import CrawlSource, RobotsStatus
from src.repository.source_repository import SourceRepository
from src.services.robots_handler import RobotsHandler, RobotsInfo
from src.services.sitemap_parser import SitemapEntry, SitemapParser


logger = logging.getLogger(__name__)


class SiteDiscovery:
    """
    站点发现器
    负责：
    1. 检查 robots.txt
    2. 发现 Sitemap URL
    3. 解析 Sitemap 获取文章 URL
    """

    def __init__(
        self,
        session: AsyncSession,
        robots_handler: RobotsHandler | None = None,
    ) -> None:
        """
        初始化站点发现器

        Args:
            session: 数据库会话
            robots_handler: Robots 处理器（可选）
        """
        self.session = session
        self.robots_handler = robots_handler or RobotsHandler()
        self.sitemap_parser = SitemapParser()
        self.source_repo = SourceRepository(session)

    async def initialize_source(
        self,
        source_id: int,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """
        初始化爬虫源
        检查 robots.txt，发现 Sitemap

        Args:
            source_id: 源 ID
            force_refresh: 是否强制刷新

        Returns:
            初始化结果
        """
        # 获取源配置
        source_dict = await self.source_repo.get_by_id(source_id)
        if not source_dict:
            return {'success': False, 'error': 'Source not found'}

        source = self.source_repo.to_domain_model(source_dict)

        logger.info(f"Initializing source: {source.site_name}")

        result = {
            'source_id': source_id,
            'site_name': source.site_name,
            'base_url': source.base_url,
            'robots_checked': False,
            'sitemap_discovered': False,
            'success': True,
        }

        # 1. 检查 robots.txt
        robots_info = await self._check_robots(source, force_refresh)
        result.update(robots_info)

        # 2. 发现 Sitemap
        sitemap_info = await self._discover_sitemap(source, force_refresh)
        result.update(sitemap_info)

        # 3. 更新数据库
        await self._update_source_metadata(source_id, robots_info, sitemap_info)

        return result

    async def _check_robots(
        self,
        source: CrawlSource,
        force_refresh: bool,
    ) -> dict[str, Any]:
        """
        检查 robots.txt

        Args:
            source: 爬虫源
            force_refresh: 是否强制刷新

        Returns:
            检查结果
        """
        result = {
            'robots_checked': True,
            'robots_status': RobotsStatus.PENDING.value,
            'crawl_delay': None,
        }

        try:
            robots_info = await self.robots_handler.get_robots_info(
                source.base_url,
                force_refresh,
            )

            # 确定状态
            if robots_info.allowed:
                result['robots_status'] = RobotsStatus.COMPLIANT.value
            else:
                result['robots_status'] = RobotsStatus.RESTRICTED.value

            result['crawl_delay'] = robots_info.crawl_delay
            result['sitemap_count'] = len(robots_info.sitemap_urls)

            logger.info(
                f"Robots check: status={result['robots_status']}, "
                f"delay={robots_info.crawl_delay}, "
                f"sitemaps={len(robots_info.sitemap_urls)}"
            )

        except Exception as e:
            logger.error(f"Error checking robots.txt: {e}")
            result['robots_status'] = RobotsStatus.ERROR.value
            result['error'] = str(e)

        return result

    async def _discover_sitemap(
        self,
        source: CrawlSource,
        force_refresh: bool,
    ) -> dict[str, Any]:
        """
        发现 Sitemap

        Args:
            source: 爬虫源
            force_refresh: 是否强制刷新

        Returns:
            发现结果
        """
        result = {
            'sitemap_discovered': False,
            'sitemap_url': None,
            'sitemap_entry_count': None,
        }

        try:
            # 从 robots.txt 提取 Sitemap URL
            sitemap_urls = await self.robots_handler.extract_sitemap_urls(
                source.base_url,
                force_refresh,
            )

            if not sitemap_urls:
                # 尝试默认位置
                sitemap_urls = [f"{source.base_url}/sitemap.xml"]

            # 使用第一个 Sitemap
            primary_sitemap = sitemap_urls[0]
            result['sitemap_url'] = primary_sitemap

            # 获取上次爬取时间
            last_crawled = source.sitemap_last_fetched

            # 解析 Sitemap（仅统计数量，不获取全部 URL）
            async with self.sitemap_parser:
                entries = await self.sitemap_parser.parse_recursive(
                    primary_sitemap,
                    last_crawled_at=last_crawled,
                )

            result['sitemap_entry_count'] = len(entries)
            result['sitemap_discovered'] = True

            logger.info(
                f"Sitemap discovered: {primary_sitemap}, "
                f"entries={len(entries)}"
            )

        except Exception as e:
            logger.error(f"Error discovering sitemap: {e}")
            result['error'] = str(e)

        return result

    async def _update_source_metadata(
        self,
        source_id: int,
        robots_info: dict[str, Any],
        sitemap_info: dict[str, Any],
    ) -> None:
        """
        更新源元数据到数据库

        Args:
            source_id: 源 ID
            robots_info: Robots 信息
            sitemap_info: Sitemap 信息
        """
        from src.core.models import SourceUpdate

        update_data = SourceUpdate()

        # Robots 信息
        if robots_info.get('robots_status'):
            # 这里需要直接更新，因为模型没有这个字段
            pass

        if robots_info.get('crawl_delay') is not None:
            # 需要使用 SQL 直接更新
            await self._update_source_field(
                source_id,
                'crawl_delay',
                robots_info['crawl_delay'],
            )

        # Sitemap 信息
        if sitemap_info.get('sitemap_url'):
            await self._update_source_field(
                source_id,
                'sitemap_url',
                sitemap_info['sitemap_url'],
            )

        if sitemap_info.get('sitemap_entry_count') is not None:
            await self._update_source_field(
                source_id,
                'sitemap_entry_count',
                sitemap_info['sitemap_entry_count'],
            )

        # 更新时间戳
        await self._update_source_field(
            source_id,
            'robots_fetched_at',
            datetime.now(),
        )

        await self._update_source_field(
            source_id,
            'sitemap_last_fetched',
            datetime.now(),
        )

    async def _update_source_field(
        self,
        source_id: int,
        field: str,
        value: Any,
    ) -> None:
        """
        更新源的单个字段

        Args:
            source_id: 源 ID
            field: 字段名
            value: 字段值
        """
        sql = f"UPDATE crawl_sources SET {field} = :value, updated_at = :updated WHERE id = :id"
        await self.source_repo.execute(
            sql,
            {'value': value, 'updated': datetime.now(), 'id': source_id},
        )

    async def discover_urls(
        self,
        source_id: int,
        limit: int | None = None,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[str]:
        """
        从 Sitemap 发现 URL

        Args:
            source_id: 源 ID
            limit: 最大 URL 数量
            include_patterns: 包含模式
            exclude_patterns: 排除模式

        Returns:
            URL 列表
        """
        # 获取源配置
        source_dict = await self.source_repo.get_by_id(source_id)
        if not source_dict:
            return []

        sitemap_url = source_dict.get('sitemap_url')
        if not sitemap_url:
            logger.warning(f"No sitemap URL configured for source {source_id}")
            return []

        # 获取上次爬取时间
        last_crawled = source_dict.get('sitemap_last_fetched')

        try:
            # 解析 Sitemap
            async with self.sitemap_parser:
                entries = await self.sitemap_parser.parse_recursive(
                    sitemap_url,
                    last_crawled_at=last_crawled,
                )

            # 过滤
            if include_patterns or exclude_patterns:
                entries = self.sitemap_parser.filter_by_pattern(
                    entries,
                    include_patterns=include_patterns,
                    exclude_patterns=exclude_patterns,
                )

            # 提取 URL
            urls = [e.loc for e in entries]

            # 限制数量
            if limit:
                urls = urls[:limit]

            logger.info(f"Discovered {len(urls)} URLs from sitemap")

            return urls

        except Exception as e:
            logger.error(f"Error discovering URLs: {e}")
            return []

    async def can_fetch(
        self,
        url: str,
        source_id: int,
    ) -> bool:
        """
        检查是否允许爬取

        Args:
            url: 目标 URL
            source_id: 源 ID

        Returns:
            是否允许
        """
        source_dict = await self.source_repo.get_by_id(source_id)
        if not source_dict:
            return True

        base_url = source_dict['base_url']
        return self.robots_handler.can_fetch(url, base_url)

    def get_effective_crawl_delay(self, source_id: int) -> float:
        """
        获取有效的爬取延迟

        Args:
            source_id: 源 ID

        Returns:
            延迟秒数
        """
        # 这里需要从缓存或数据库读取
        # 简化实现，返回默认值
        return 1.0

    async def close(self) -> None:
        """关闭资源"""
        await self.sitemap_parser.close()


# 便捷函数
async def initialize_source(source_id: int, session: AsyncSession) -> dict[str, Any]:
    """
    便捷函数：初始化爬虫源

    Args:
        source_id: 源 ID
        session: 数据库会话

    Returns:
        初始化结果
    """
    discovery = SiteDiscovery(session)
    return await discovery.initialize_source(source_id)


async def discover_urls_from_sitemap(
    source_id: int,
    session: AsyncSession,
    limit: int | None = None,
) -> list[str]:
    """
    便捷函数：从 Sitemap 发现 URL

    Args:
        source_id: 源 ID
        session: 数据库会话
        limit: 最大 URL 数量

    Returns:
        URL 列表
    """
    discovery = SiteDiscovery(session)
    return await discovery.discover_urls(source_id, limit=limit)
