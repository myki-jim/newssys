"""
统一爬虫服务
使用配置化的 CSS 选择器从任意新闻源提取内容
"""

import asyncio
import random
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
import html2text

from src.core.models import ArticleCreate, ArticleStatus, CrawlSource
from src.services.time_extractor import TimeExtractor


def is_image_url(url: str) -> bool:
    """检查URL是否是图片URL"""
    if not url:
        return False

    # 常见图片扩展名
    image_extensions = {
        '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg',
        '.JPG', '.JPEG', '.PNG', '.GIF', '.WEBP', '.BMP', '.SVG',
    }

    parsed = urlparse(url)
    path = parsed.path.lower()

    # 检查文件扩展名
    for ext in image_extensions:
        if path.endswith(ext.lower()):
            return True

    # 检查常见的CDN图片路径特征
    if any(keyword in path for keyword in ['/image', '/img', '/photo', '/upload', '/media', '/static']):
        return True

    # 如果URL太长且包含html, php, aspx等，可能是网页链接
    if any(ext in path for ext in ['.html', '.htm', '.php', '.aspx', '.jsp']):
        return False

    return False


class ScraperConfig:
    """爬虫配置"""

    # 默认请求头
    DEFAULT_HEADERS = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,ru;q=0.7',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }

    # User-Agent 池
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]


class UniversalScraper:
    """
    统一爬虫服务
    从配置化的新闻源提取文章内容
    """

    def __init__(
        self,
        timeout: int = 30,
        retry_times: int = 3,
        retry_delay: int = 1,
        proxy: str | None = None,
    ) -> None:
        """
        初始化爬虫

        Args:
            timeout: 请求超时时间（秒）
            retry_times: 重试次数
            retry_delay: 重试延迟（秒）
            proxy: 代理地址
        """
        self.timeout = timeout
        self.retry_times = retry_times
        self.retry_delay = retry_delay
        self.proxy = proxy
        self.time_extractor = TimeExtractor()

        # 创建 HTTP 客户端
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "UniversalScraper":
        """异步上下文管理器入口"""
        await self._init_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """异步上下文管理器退出"""
        await self._close_client()

    async def _init_client(self) -> None:
        """初始化 HTTP 客户端"""
        if self._client is None:
            limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                limits=limits,
                proxy=self.proxy,
                http2=True,
                verify=False,  # 仅用于开发环境
            )

    async def _close_client(self) -> None:
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_headers(self) -> dict[str, str]:
        """获取随机请求头"""
        headers = ScraperConfig.DEFAULT_HEADERS.copy()
        headers['User-Agent'] = random.choice(ScraperConfig.USER_AGENTS)
        return headers

    async def fetch_html(self, url: str) -> str | None:
        """
        获取 HTML 内容
        支持重试机制

        Args:
            url: 目标 URL

        Returns:
            HTML 内容，失败返回 None
        """
        await self._init_client()
        assert self._client is not None

        headers = self._get_headers()

        for attempt in range(self.retry_times):
            try:
                response = await self._client.get(url, headers=headers, follow_redirects=True)
                response.raise_for_status()

                # 自动检测编码
                response.encoding = response.encoding or 'utf-8'
                return response.text

            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self.retry_times - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                return None

            except (httpx.RequestError, httpx.TimeoutException) as e:
                if attempt < self.retry_times - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                return None

        return None

    async def scrape_article(
        self,
        url: str,
        source: CrawlSource,
    ) -> ArticleCreate | None:
        """
        爬取单篇文章

        Args:
            url: 文章 URL
            source: 爬虫源配置

        Returns:
            ArticleCreate 对象，失败返回 None
        """
        # 获取 HTML
        html = await self.fetch_html(url)
        if not html:
            return None

        # 解析 HTML
        soup = BeautifulSoup(html, 'lxml')

        # 根据 parser_config 提取内容
        config = source.parser_config

        # 提取标题
        title = self._extract_text(soup, config.title_selector)
        if not title:
            return None

        # 提取正文
        content = self._extract_content(soup, config.content_selector)
        if not content:
            return None

        # 提取发布时间
        publish_time = self.time_extractor.extract_publish_time(
            html,
            url,
            languages=['zh', 'ru', 'kk', 'en'],
        )

        # 提取作者（可选）
        author = None
        if config.author_selector:
            author = self._extract_text(soup, config.author_selector)

        # 提取图片和标签
        extra_data = self._extract_media_and_tags(soup, config, url)

        return ArticleCreate(
            url=url,
            title=title,
            content=content,
            publish_time=publish_time,
            author=author,
            source_id=source.id or 0,
            extra_data=extra_data,
        )

    def _extract_text(self, soup: BeautifulSoup, selector: str) -> str | None:
        """
        提取文本内容

        Args:
            soup: BeautifulSoup 对象
            selector: CSS 选择器

        Returns:
            提取的文本，失败返回 None
        """
        if not selector:
            return None

        element = soup.select_one(selector)
        if not element:
            return None

        # 获取文本并清理
        text = element.get_text(separator=' ', strip=True)
        return text if text else None

    def _extract_content(self, soup: BeautifulSoup, selector: str) -> str | None:
        """
        提取正文内容并转换为 Markdown

        Args:
            soup: BeautifulSoup 对象
            selector: CSS 选择器

        Returns:
            Markdown 格式的正文，失败返回 None
        """
        if not selector:
            return None

        element = soup.select_one(selector)
        if not element:
            return None

        # 清理HTML：移除错误的img标签
        for img in element.find_all('img', src=True):
            img_src = img.get('src')
            if img_src and not is_image_url(img_src):
                # 移除不是真实图片的img标签
                img.decompose()

        # 使用 html2text 转换为 Markdown
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_emphasis = False
        h.body_width = 0  # 不换行

        # 获取元素的 HTML
        html_content = str(element)
        markdown = h.handle(html_content)

        return markdown.strip() if markdown else None

    def _extract_media_and_tags(
        self,
        soup: BeautifulSoup,
        config: Any,
        base_url: str,
    ) -> dict[str, Any]:
        """
        提取图片和标签信息

        Args:
            soup: BeautifulSoup 对象
            config: 解析器配置
            base_url: 基础URL（用于解析相对路径）

        Returns:
            包含 images 和 tags 的 extra_data 字典
        """
        extra_data: dict[str, Any] = {}

        # 提取内容区域
        if config.content_selector:
            content_element = soup.select_one(config.content_selector)
        else:
            content_element = soup

        if not content_element:
            return extra_data

        # 提取所有图片
        images_set: set[str] = set()
        for img in content_element.find_all('img', src=True):
            img_src = img.get('src')
            if img_src:
                # 转换为绝对URL
                absolute_url = urljoin(base_url, img_src)
                # 只保留真正的图片URL
                if is_image_url(absolute_url):
                    images_set.add(absolute_url)

        # 也检查 picture source 标签
        for source in content_element.find_all('source', srcset=True):
            srcset = source.get('srcset', '')
            for src_item in srcset.split(','):
                img_url = src_item.strip().split()[0]  # 取URL部分，忽略宽度描述
                if img_url:
                    absolute_url = urljoin(base_url, img_url)
                    if is_image_url(absolute_url):
                        images_set.add(absolute_url)

        if images_set:
            extra_data['images'] = list(images_set)

        # 提取标签（如果有的话）
        tags_set: set[str] = set()
        for meta in soup.find_all('meta', property='article:tag'):
            tag = meta.get('content')
            if tag:
                tags_set.add(tag)

        for meta in soup.find_all('meta', attrs={'name': 'keywords'}):
            keywords = meta.get('content', '')
            if keywords:
                # 关键词可能是逗号分隔的
                for kw in keywords.split(','):
                    kw = kw.strip()
                    if kw:
                        tags_set.add(kw)

        if tags_set:
            extra_data['tags'] = list(tags_set)[:10]  # 最多10个标签

        return extra_data

    async def discover_article_urls(
        self,
        source: CrawlSource,
        max_pages: int = 5,
    ) -> list[str]:
        """
        从列表页发现文章 URL

        Args:
            source: 爬虫源配置
            max_pages: 最大翻页数

        Returns:
            文章 URL 列表
        """
        if not source.parser_config.list_selector:
            # 如果没有配置列表选择器，返回空列表
            return []

        urls: set[str] = set()

        for page in range(1, max_pages + 1):
            # 构造列表页 URL
            list_url = self._build_list_url(source, page)

            # 获取 HTML
            html = await self.fetch_html(list_url)
            if not html:
                continue

            # 解析 URL
            soup = BeautifulSoup(html, 'lxml')
            page_urls = self._extract_urls_from_list(soup, source)

            urls.update(page_urls)

            # 如果没有更多 URL，停止翻页
            if not page_urls:
                break

        return list(urls)

    def _build_list_url(self, source: CrawlSource, page: int) -> str:
        """
        构造列表页 URL

        Args:
            source: 爬虫源配置
            page: 页码

        Returns:
            列表页 URL
        """
        base_url = source.base_url

        # 简单的分页处理
        if page == 1:
            return base_url
        else:
            # 尝试常见的分页格式
            parsed = urlparse(base_url)
            path = parsed.path.rstrip('/')

            # 尝试 /page/2 格式
            return f"{parsed.scheme}://{parsed.netloc}{path}/page/{page}/"

    def _extract_urls_from_list(
        self,
        soup: BeautifulSoup,
        source: CrawlSource,
    ) -> list[str]:
        """
        从列表页提取文章 URL

        Args:
            soup: BeautifulSoup 对象
            source: 爬虫源配置

        Returns:
            文章 URL 列表
        """
        config = source.parser_config
        urls: list[str] = []

        if config.url_selector:
            # 使用配置的选择器
            elements = soup.select(config.url_selector)
            for element in elements:
                href = element.get('href')
                if href:
                    full_url = urljoin(source.base_url, href)
                    urls.append(full_url)
        else:
            # 尝试从 list_selector 的子元素中提取
            list_elements = soup.select(config.list_selector)
            for element in list_elements:
                # 查找链接
                link = element.find('a', href=True)
                if link:
                    href = link['href']
                    full_url = urljoin(source.base_url, href)
                    urls.append(full_url)

        return urls

    async def scrape_batch(
        self,
        urls: list[str],
        source: CrawlSource,
        concurrent_limit: int = 5,
    ) -> list[ArticleCreate]:
        """
        批量爬取文章

        Args:
            urls: URL 列表
            source: 爬虫源配置
            concurrent_limit: 并发限制

        Returns:
            成功爬取的文章列表
        """
        semaphore = asyncio.Semaphore(concurrent_limit)

        async def scrape_with_semaphore(url: str) -> ArticleCreate | None:
            async with semaphore:
                return await self.scrape_article(url, source)

        tasks = [scrape_with_semaphore(url) for url in urls]
        results = await asyncio.gather(*tasks)

        return [r for r in results if r is not None]
