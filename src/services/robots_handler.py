"""
Robots 协议处理器
解析 robots.txt，检查抓取权限，识别 Crawl-delay，提取 Sitemap URL
"""

import logging
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx


logger = logging.getLogger(__name__)


class RobotsInfo:
    """
    Robots.txt 信息
    """

    def __init__(
        self,
        base_url: str,
        allowed: bool = True,
        crawl_delay: float | None = None,
        sitemap_urls: list[str] | None = None,
    ) -> None:
        """
        初始化 Robots 信息

        Args:
            base_url: 基础 URL
            allowed: 是否允许爬取
            crawl_delay: 爬取延迟（秒）
            sitemap_urls: Sitemap URL 列表
        """
        self.base_url = base_url
        self.allowed = allowed
        self.crawl_delay = crawl_delay
        self.sitemap_urls = sitemap_urls or []

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            'base_url': self.base_url,
            'allowed': self.allowed,
            'crawl_delay': self.crawl_delay,
            'sitemap_urls': self.sitemap_urls,
        }


class RobotsHandler:
    """
    Robots 协议处理器
    负责解析和遵守 robots.txt 规则
    """

    # 默认 User-Agent
    DEFAULT_USER_AGENT = "NewsBot"

    # 缓存过期时间（秒）
    CACHE_EXPIRY = 3600

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = 10,
    ) -> None:
        """
        初始化 Robots 处理器

        Args:
            user_agent: User-Agent 名称
            timeout: 请求超时时间（秒）
        """
        self.user_agent = user_agent
        self.timeout = timeout

        # Robots.txt 缓存 {base_url: (RobotFileParser, fetched_at)}
        self._cache: dict[str, tuple[RobotFileParser, datetime]] = {}

        # Sitemap URL 缓存 {base_url: (sitemap_urls, fetched_at)}
        self._sitemap_cache: dict[str, tuple[list[str], datetime]] = {}

    def _get_robots_url(self, base_url: str) -> str:
        """
        获取 robots.txt URL

        Args:
            base_url: 基础 URL

        Returns:
            robots.txt URL
        """
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    async def fetch_robots_txt(
        self,
        base_url: str,
        force_refresh: bool = False,
    ) -> RobotFileParser | None:
        """
        获取并解析 robots.txt

        Args:
            base_url: 基础 URL
            force_refresh: 是否强制刷新缓存

        Returns:
            RobotFileParser 对象，获取失败返回 None
        """
        # 检查缓存
        if not force_refresh and base_url in self._cache:
            parser, fetched_at = self._cache[base_url]
            age = (datetime.now() - fetched_at).total_seconds()
            if age < self.CACHE_EXPIRY:
                logger.debug(f"Using cached robots.txt for {base_url}")
                return parser

        robots_url = self._get_robots_url(base_url)
        logger.info(f"Fetching robots.txt: {robots_url}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(robots_url, follow_redirects=True)

                # 404 表示没有 robots.txt
                if response.status_code == 404:
                    logger.info(f"No robots.txt found for {base_url}")
                    return None

                response.raise_for_status()

                # 创建 RobotFileParser 并读取内容
                parser = RobotFileParser()
                parser.parse(response.text.splitlines())

                # 更新缓存
                self._cache[base_url] = (parser, datetime.now())

                return parser

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching robots.txt: {e}")
            return None

        except httpx.RequestError as e:
            logger.error(f"Request error fetching robots.txt: {e}")
            return None

    def can_fetch(
        self,
        url: str,
        base_url: str,
        user_agent: str | None = None,
    ) -> bool:
        """
        检查是否允许爬取指定 URL

        Args:
            url: 目标 URL
            base_url: 基础 URL
            user_agent: User-Agent（默认使用实例的 user_agent）

        Returns:
            是否允许爬取
        """
        if base_url not in self._cache:
            logger.warning(f"No robots.txt cached for {base_url}, allowing by default")
            return True

        parser, _ = self._cache[base_url]
        ua = user_agent or self.user_agent

        allowed = parser.can_fetch(ua, url)

        if not allowed:
            logger.warning(f"robots.txt disallows: {url}")

        return allowed

    def get_crawl_delay(
        self,
        base_url: str,
        user_agent: str | None = None,
    ) -> float | None:
        """
        获取爬取延迟

        Args:
            base_url: 基础 URL
            user_agent: User-Agent

        Returns:
            延迟秒数，未指定返回 None
        """
        if base_url not in self._cache:
            return None

        parser, _ = self._cache[base_url]
        ua = user_agent or self.user_agent

        delay = parser.crawl_delay(ua)

        if delay:
            logger.info(f"Crawl-delay for {base_url}: {delay}s")

        return delay

    def get_request_rate(
        self,
        base_url: str,
        user_agent: str | None = None,
    ) -> tuple[int, int] | None:
        """
        获取请求速率限制

        Args:
            base_url: 基础 URL
            user_agent: User-Agent

        Returns:
            (请求数, 时间秒数) 元组，未指定返回 None
        """
        if base_url not in self._cache:
            return None

        parser, _ = self._cache[base_url]
        ua = user_agent or self.user_agent

        return parser.request_rate(ua)

    async def extract_sitemap_urls(
        self,
        base_url: str,
        force_refresh: bool = False,
    ) -> list[str]:
        """
        从 robots.txt 提取 Sitemap URL

        Args:
            base_url: 基础 URL
            force_refresh: 是否强制刷新

        Returns:
            Sitemap URL 列表
        """
        # 检查缓存
        if not force_refresh and base_url in self._sitemap_cache:
            urls, fetched_at = self._sitemap_cache[base_url]
            age = (datetime.now() - fetched_at).total_seconds()
            if age < self.CACHE_EXPIRY:
                return urls

        # 获取 robots.txt
        parser = await self.fetch_robots_txt(base_url, force_refresh)
        if parser is None:
            self._sitemap_cache[base_url] = ([], datetime.now())
            return []

        # 提取 Sitemap URL
        sitemap_urls = []

        # RobotFileParser 不直接存储 Sitemap，需要重新解析
        robots_url = self._get_robots_url(base_url)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(robots_url, follow_redirects=True)
                response.raise_for_status()

                for line in response.text.splitlines():
                    line = line.strip()
                    if line.lower().startswith('sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        # 验证 URL 格式
                        if sitemap_url.startswith(('http://', 'https://')):
                            sitemap_urls.append(sitemap_url)
                        else:
                            # 相对 URL，转换为绝对 URL
                            full_url = urljoin(base_url, sitemap_url)
                            sitemap_urls.append(full_url)

                logger.info(f"Found {len(sitemap_urls)} sitemap(s) in robots.txt")

        except Exception as e:
            logger.error(f"Error extracting sitemap URLs: {e}")

        self._sitemap_cache[base_url] = (sitemap_urls, datetime.now())
        return sitemap_urls

    async def get_robots_info(
        self,
        base_url: str,
        force_refresh: bool = False,
    ) -> RobotsInfo:
        """
        获取完整的 Robots 信息

        Args:
            base_url: 基础 URL
            force_refresh: 是否强制刷新

        Returns:
            RobotsInfo 对象
        """
        # 获取 robots.txt
        parser = await self.fetch_robots_txt(base_url, force_refresh)

        # 如果没有 robots.txt，返回允许访问
        if parser is None:
            return RobotsInfo(
                base_url=base_url,
                allowed=True,
                crawl_delay=None,
                sitemap_urls=[],
            )

        # 检查是否允许访问根路径
        allowed = parser.can_fetch(self.user_agent, base_url + '/')

        # 获取爬取延迟
        crawl_delay = self.get_crawl_delay(base_url)

        # 获取 Sitemap URL
        sitemap_urls = await self.extract_sitemap_urls(base_url, force_refresh)

        return RobotsInfo(
            base_url=base_url,
            allowed=allowed,
            crawl_delay=crawl_delay,
            sitemap_urls=sitemap_urls,
        )

    def clear_cache(self, base_url: str | None = None) -> None:
        """
        清除缓存

        Args:
            base_url: 指定清除的 URL，None 表示清除全部
        """
        if base_url:
            self._cache.pop(base_url, None)
            self._sitemap_cache.pop(base_url, None)
        else:
            self._cache.clear()
            self._sitemap_cache.clear()

    def get_cache_stats(self) -> dict[str, Any]:
        """
        获取缓存统计

        Returns:
            缓存统计信息
        """
        return {
            'robots_cache_size': len(self._cache),
            'sitemap_cache_size': len(self._sitemap_cache),
            'cached_urls': list(self._cache.keys()),
        }


# 全局 Robots 处理器实例
_robots_handler: RobotsHandler | None = None


def get_robots_handler() -> RobotsHandler:
    """
    获取全局 Robots 处理器单例

    Returns:
        RobotsHandler 实例
    """
    global _robots_handler
    if _robots_handler is None:
        _robots_handler = RobotsHandler()
    return _robots_handler
