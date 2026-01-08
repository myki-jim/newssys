"""
递归 Sitemap 解析器
支持嵌套 Sitemap Index、增量同步、多种格式
增强鲁棒性：robots.txt 解析、User-Agent 优化、错误重试
"""

import gzip
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from lxml import etree


logger = logging.getLogger(__name__)


# 标准 User-Agent 列表（避免被拦截）
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
]


@dataclass
class SitemapEntry:
    """
    Sitemap 条目
    """

    loc: str  # URL
    lastmod: datetime | None = None  # 最后修改时间
    changefreq: str | None = None  # 更新频率
    priority: float | None = None  # 优先级 (0.0-1.0)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            'loc': self.loc,
            'lastmod': self.lastmod.isoformat() if self.lastmod else None,
            'changefreq': self.changefreq,
            'priority': self.priority,
        }

    def __hash__(self) -> int:
        return hash(self.loc)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, SitemapEntry):
            return self.loc == other.loc
        return False


@dataclass
class SitemapIndexEntry:
    """
    Sitemap 索引条目
    指向子 Sitemap
    """

    loc: str  # 子 Sitemap URL
    lastmod: datetime | None = None  # 最后修改时间

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            'loc': self.loc,
            'lastmod': self.lastmod.isoformat() if self.lastmod else None,
        }


class SitemapParser:
    """
    Sitemap 解析器
    支持递归解析 Sitemap Index 和增量同步
    """

    # XML 命名空间
    NAMESPACES = {
        'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9',
    }

    # 最大递归深度
    MAX_DEPTH = 5

    # 最大 URL 数量
    MAX_URLS = 100000

    def __init__(
        self,
        timeout: int = 30,
        max_depth: int = MAX_DEPTH,
        max_urls: int = MAX_URLS,
    ) -> None:
        """
        初始化 Sitemap 解析器

        Args:
            timeout: 请求超时时间（秒）
            max_depth: 最大递归深度
            max_urls: 最大 URL 数量
        """
        self.timeout = timeout
        self.max_depth = max_depth
        self.max_urls = max_urls

        self._client: httpx.AsyncClient | None = None
        self._url_count = 0

    async def __aenter__(self) -> "SitemapParser":
        """异步上下文管理器入口"""
        await self._init_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """异步上下文管理器退出"""
        await self._close_client()

    async def _init_client(self) -> None:
        """初始化 HTTP 客户端"""
        if self._client is None:
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ru;q=0.7,kk;q=0.6",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                headers=headers,
            )

    async def _close_client(self) -> None:
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def discover_sitemap_from_robots(self, base_url: str) -> list[str]:
        """
        从 robots.txt 发现 Sitemap URL

        Args:
            base_url: 站点基础 URL

        Returns:
            Sitemap URL 列表
        """
        await self._init_client()
        assert self._client is not None

        robots_url = urljoin(base_url, "/robots.txt")
        sitemaps: list[str] = []

        logger.info(f"Trying to discover sitemap from robots.txt: {robots_url}")

        try:
            response = await self._client.get(robots_url)
            if response.status_code == 200:
                lines = response.text.splitlines()
                for line in lines:
                    line = line.strip()
                    if line.lower().startswith("sitemap:"):
                        sitemap_url = line.split(":", 1)[1].strip()
                        if sitemap_url:
                            sitemaps.append(sitemap_url)
                            logger.info(f"Found sitemap in robots.txt: {sitemap_url}")
            else:
                logger.debug(f"robots.txt returned status {response.status_code}")

        except Exception as e:
            logger.debug(f"Error fetching robots.txt: {e}")

        return sitemaps

    async def fetch_sitemap(
        self,
        url: str,
    ) -> bytes | None:
        """
        获取 Sitemap 内容
        支持普通 XML 和 gzip 压缩格式

        Args:
            url: Sitemap URL

        Returns:
            Sitemap 内容（bytes）
        """
        await self._init_client()
        assert self._client is not None

        logger.info(f"Fetching sitemap: {url}")

        try:
            response = await self._client.get(url)
            response.raise_for_status()

            content = response.content

            # 检查是否是 gzip 压缩
            if url.endswith('.gz') or response.headers.get('content-encoding') == 'gzip':
                try:
                    content = gzip.decompress(content)
                    logger.debug("Decompressed gzipped sitemap")
                except gzip.BadGzipFile:
                    # 可能不是真正的 gzip 文件
                    pass

            return content

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching sitemap: {e}")
            return None

        except httpx.RequestError as e:
            logger.error(f"Request error fetching sitemap: {e}")
            return None

    def parse_sitemap_xml(
        self,
        content: bytes,
        base_url: str,
    ) -> tuple[list[SitemapEntry], list[SitemapIndexEntry]]:
        """
        解析 Sitemap XML 内容
        使用流式解析避免内存溢出

        Args:
            content: XML 内容
            base_url: 基础 URL（用于解析相对 URL）

        Returns:
            (URL 条目列表, Sitemap Index 条目列表)
        """
        urls: list[SitemapEntry] = []
        sitemaps: list[SitemapIndexEntry] = []

        try:
            # 使用 iterparse 进行流式解析
            context = etree.iterparse(BytesIO(content), events=('end',), recover=True)

            for event, elem in context:
                tag = etree.QName(elem.tag).localname

                # 处理 URL 条目
                if tag == 'url':
                    entry = self._parse_url_element(elem)
                    if entry:
                        urls.append(entry)
                    # 清理已处理的元素
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]

                # 处理 Sitemap Index 条目
                elif tag == 'sitemap':
                    entry = self._parse_sitemap_element(elem)
                    if entry:
                        sitemaps.append(entry)
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]

            # 清理根元素
            if context.root is not None:
                context.root.clear()

        except etree.XMLSyntaxError as e:
            logger.error(f"XML syntax error: {e}")

        except Exception as e:
            logger.error(f"Error parsing sitemap XML: {e}")

        logger.info(f"Parsed {len(urls)} URLs and {len(sitemaps)} sitemap indexes")
        return urls, sitemaps

    def _parse_url_element(self, elem: etree.Element) -> SitemapEntry | None:
        """
        解析 <url> 元素

        Args:
            elem: XML 元素

        Returns:
            SitemapEntry 对象
        """
        try:
            # 提取 loc (URL)
            loc_elem = elem.find('sm:loc', self.NAMESPACES)
            if loc_elem is None:
                loc_elem = elem.find('loc')
            if loc_elem is None or not loc_elem.text:
                return None

            loc = loc_elem.text.strip()

            # 提取 lastmod
            lastmod = None
            lastmod_elem = elem.find('sm:lastmod', self.NAMESPACES)
            if lastmod_elem is None:
                lastmod_elem = elem.find('lastmod')
            if lastmod_elem is not None and lastmod_elem.text:
                try:
                    lastmod = self._parse_datetime(lastmod_elem.text.strip())
                except ValueError:
                    pass

            # 提取 changefreq
            changefreq = None
            changefreq_elem = elem.find('sm:changefreq', self.NAMESPACES)
            if changefreq_elem is None:
                changefreq_elem = elem.find('changefreq')
            if changefreq_elem is not None and changefreq_elem.text:
                changefreq = changefreq_elem.text.strip()

            # 提取 priority
            priority = None
            priority_elem = elem.find('sm:priority', self.NAMESPACES)
            if priority_elem is None:
                priority_elem = elem.find('priority')
            if priority_elem is not None and priority_elem.text:
                try:
                    priority = float(priority_elem.text.strip())
                except ValueError:
                    pass

            return SitemapEntry(
                loc=loc,
                lastmod=lastmod,
                changefreq=changefreq,
                priority=priority,
            )

        except Exception as e:
            logger.debug(f"Error parsing URL element: {e}")
            return None

    def _parse_sitemap_element(self, elem: etree.Element) -> SitemapIndexEntry | None:
        """
        解析 <sitemap> 元素

        Args:
            elem: XML 元素

        Returns:
            SitemapIndexEntry 对象
        """
        try:
            # 提取 loc
            loc_elem = elem.find('sm:loc', self.NAMESPACES)
            if loc_elem is None:
                loc_elem = elem.find('loc')
            if loc_elem is None or not loc_elem.text:
                return None

            loc = loc_elem.text.strip()

            # 提取 lastmod
            lastmod = None
            lastmod_elem = elem.find('sm:lastmod', self.NAMESPACES)
            if lastmod_elem is None:
                lastmod_elem = elem.find('lastmod')
            if lastmod_elem is not None and lastmod_elem.text:
                try:
                    lastmod = self._parse_datetime(lastmod_elem.text.strip())
                except ValueError:
                    pass

            return SitemapIndexEntry(
                loc=loc,
                lastmod=lastmod,
            )

        except Exception as e:
            logger.debug(f"Error parsing sitemap element: {e}")
            return None

    @staticmethod
    def _parse_datetime(date_str: str) -> datetime | None:
        """
        解析日期时间字符串
        支持 ISO 8601 格式
        所有解析出的 datetime 都带时区信息（默认 UTC）
        """
        # 首先处理 'Z' 后缀（表示 UTC）
        if date_str.endswith('Z'):
            date_str = date_str[:-1] + '+00:00'

        formats = [
            '%Y-%m-%dT%H:%M:%S%z',  # 带时区
            '%Y-%m-%dT%H:%M:%S',     # 不带时区
            '%Y-%m-%d',              # 只有日期
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # 如果没有时区信息，添加 UTC 时区
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue

        return None

    async def parse_recursive(
        self,
        sitemap_url: str,
        last_crawled_at: datetime | None = None,
        depth: int = 0,
    ) -> list[SitemapEntry]:
        """
        递归解析 Sitemap
        处理嵌套的 Sitemap Index

        Args:
            sitemap_url: Sitemap URL
            last_crawled_at: 上次爬取时间（用于增量同步）
            depth: 当前递归深度

        Returns:
            所有 URL 条目
        """
        if depth > self.max_depth:
            logger.warning(f"Maximum recursion depth {self.max_depth} reached")
            return []

        if self._url_count >= self.max_urls:
            logger.warning(f"Maximum URL count {self.max_urls} reached")
            return []

        logger.info(f"Parsing sitemap (depth={depth}): {sitemap_url}")

        # 统一时区：如果 last_crawled_at 是 naive datetime，添加 UTC 时区
        if last_crawled_at is not None and last_crawled_at.tzinfo is None:
            last_crawled_at = last_crawled_at.replace(tzinfo=timezone.utc)

        # 获取 Sitemap 内容
        content = await self.fetch_sitemap(sitemap_url)
        if content is None:
            return []

        # 解析 XML
        urls, sitemaps = self.parse_sitemap_xml(content, sitemap_url)

        # 增量同步：过滤未更新的 URL
        if last_crawled_at:
            urls = [u for u in urls if u.lastmod is None or u.lastmod > last_crawled_at]
            logger.info(f"Incremental sync: {len(urls)} URLs updated since {last_crawled_at}")

        # 添加到结果
        result = urls.copy()
        self._url_count += len(urls)

        # 递归处理子 Sitemap
        for sitemap_entry in sitemaps:
            # 检查子 Sitemap 是否需要更新
            if last_crawled_at and sitemap_entry.lastmod:
                if sitemap_entry.lastmod <= last_crawled_at:
                    logger.info(f"Skipping unchanged sitemap: {sitemap_entry.loc}")
                    continue

            # 递归解析
            child_urls = await self.parse_recursive(
                sitemap_entry.loc,
                last_crawled_at,
                depth + 1,
            )
            result.extend(child_urls)

        return result

    async def parse_text_sitemap(self, url: str) -> list[SitemapEntry]:
        """
        解析纯文本格式的 Sitemap
        每行一个 URL

        Args:
            url: Sitemap URL

        Returns:
            URL 条目列表
        """
        await self._init_client()
        assert self._client is not None

        logger.info(f"Parsing text sitemap: {url}")

        try:
            response = await self._client.get(url)
            response.raise_for_status()

            lines = response.text.splitlines()
            entries = []

            for line in lines:
                url = line.strip()
                if url and url.startswith(('http://', 'https://')):
                    entries.append(SitemapEntry(loc=url))

            logger.info(f"Parsed {len(entries)} URLs from text sitemap")
            return entries

        except Exception as e:
            logger.error(f"Error parsing text sitemap: {e}")
            return []

    async def parse(
        self,
        sitemap_url: str,
        last_crawled_at: datetime | None = None,
    ) -> list[SitemapEntry]:
        """
        解析 Sitemap（自动检测格式）
        如果直接访问失败，尝试从 robots.txt 发现 Sitemap URL

        Args:
            sitemap_url: Sitemap URL
            last_crawled_at: 上次爬取时间

        Returns:
            URL 条目列表
        """
        self._url_count = 0

        # 统一时区：如果 last_crawled_at 是 naive datetime，添加 UTC 时区
        if last_crawled_at is not None and last_crawled_at.tzinfo is None:
            last_crawled_at = last_crawled_at.replace(tzinfo=timezone.utc)

        # 尝试直接获取 Sitemap
        content = await self.fetch_sitemap(sitemap_url)
        if content is None:
            # 失败时尝试从 robots.txt 发现
            logger.warning(f"Failed to fetch {sitemap_url}, trying robots.txt discovery")
            base_url = f"{urlparse(sitemap_url).scheme}://{urlparse(sitemap_url).netloc}"
            discovered_sitemaps = await self.discover_sitemap_from_robots(base_url)

            if discovered_sitemaps:
                # 使用第一个发现的 Sitemap
                new_sitemap_url = discovered_sitemaps[0]
                logger.info(f"Using discovered sitemap: {new_sitemap_url}")
                content = await self.fetch_sitemap(new_sitemap_url)
                if content is not None:
                    sitemap_url = new_sitemap_url
                else:
                    return []
            else:
                logger.error(f"No sitemap found in robots.txt for {base_url}")
                return []

        # 检查是否是 XML
        content_str = content[:100].decode('utf-8', errors='ignore')
        if '<?xml' in content_str or '<urlset' in content_str or '<sitemapindex' in content_str:
            return await self.parse_recursive(sitemap_url, last_crawled_at)

        # 尝试纯文本格式
        return await self.parse_text_sitemap(sitemap_url)

    def filter_by_pattern(
        self,
        entries: list[SitemapEntry],
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> list[SitemapEntry]:
        """
        按模式过滤 URL

        Args:
            entries: URL 条目列表
            include_patterns: 包含模式列表
            exclude_patterns: 排除模式列表

        Returns:
            过滤后的条目列表
        """
        import re

        result = entries

        # 应用包含模式
        if include_patterns:
            patterns = [re.compile(p) for p in include_patterns]
            result = [
                e for e in result
                if any(p.search(e.loc) for p in patterns)
            ]

        # 应用排除模式
        if exclude_patterns:
            patterns = [re.compile(p) for p in exclude_patterns]
            result = [
                e for e in result
                if not any(p.search(e.loc) for p in patterns)
            ]

        logger.info(f"Filtered {len(entries)} entries to {len(result)}")
        return result

    async def close(self) -> None:
        """关闭资源"""
        await self._close_client()


# 便捷函数
async def parse_sitemap(
    sitemap_url: str,
    last_crawled_at: datetime | None = None,
) -> list[SitemapEntry]:
    """
    便捷函数：解析 Sitemap

    Args:
        sitemap_url: Sitemap URL
        last_crawled_at: 上次爬取时间

    Returns:
        URL 条目列表
    """
    async with SitemapParser() as parser:
        return await parser.parse(sitemap_url, last_crawled_at)
