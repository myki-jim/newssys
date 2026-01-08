"""
统一爬虫服务 (Universal Scraper)
适配层，为测试脚本提供统一的接口
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup
import html2text

from src.core.models import ParserConfig
from src.services.time_extractor import TimeExtractor
from src.services.smart_extractor import SmartExtractor


logger = logging.getLogger(__name__)

# 专业浏览器 User-Agent 列表（使用最新版本号降低封禁风险）
USER_AGENTS = [
    # Chrome on Windows (最新稳定版)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    # Chrome on Linux (真实服务器环境常见)
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Chrome on Android (移动端)
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
    # Safari on iOS (移动端)
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Mobile/15E148 Safari/604.1",
]


class UniversalScraper:
    """
    统一爬虫服务
    从配置化的新闻源提取文章内容
    """

    def __init__(
        self,
        timeout: int = 30,
        proxy: str | None = None,
    ) -> None:
        """
        初始化爬虫

        Args:
            timeout: 请求超时时间（秒）
            proxy: 代理地址
        """
        self.timeout = timeout
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
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                proxy=self.proxy,
                follow_redirects=True,
                verify=False,
            )

    async def _close_client(self) -> None:
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_headers(self) -> dict[str, str]:
        """获取请求头（使用随机 User-Agent 和更真实的浏览器头）"""
        ua = random.choice(USER_AGENTS)

        # 根据UA类型设置不同的Sec- headers
        if "Chrome" in ua:
            sec_ua = '"Chromium";v="131", "Not_A Brand";v="24"'
            sec_ua_platform = '"Windows"'
            sec_ua_platform_version = '"10.0.0"'
        elif "Firefox" in ua:
            sec_ua = '"Not_A Brand";v="8.0", "Chromium";v="131", "Firefox";v="133.0"'
            sec_ua_platform = '"Windows"'
            sec_ua_platform_version = '"10.0.0"'
        elif "Safari" in ua:
            sec_ua = '"Not_A Brand";v="8.0", "Chromium";v="131", "Safari";v="18.2"'
            sec_ua_platform = '"macOS"'
            sec_ua_platform_version = '"14.5"'
        else:
            sec_ua = '"Chromium";v="131", "Not_A Brand";v="24"'
            sec_ua_platform = '"Windows"'
            sec_ua_platform_version = '"10.0.0"'

        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ru;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Sec-Ch-Ua": sec_ua,
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": sec_ua_platform,
            "Sec-Ch-Ua-Platform-Version": sec_ua_platform_version,
            "Cache-Control": "max-age=0",
            "DNT": "1",
        }

    async def scrape(
        self,
        url: str,
        parser_config: ParserConfig | dict[str, Any],
        source_id: int = 0,
    ) -> Any:
        """
        爬取文章内容

        Args:
            url: 文章 URL
            parser_config: 解析器配置
            source_id: 源 ID

        Returns:
            文章对象（即使失败也返回对象，title/content 可能为 None）
        """
        await self._init_client()
        assert self._client is not None

        # 转换 parser_config
        if isinstance(parser_config, dict):
            config = ParserConfig(**parser_config)
        else:
            config = parser_config

        logger.info(f"Scraping URL: {url} with config: title_selector={config.title_selector}, content_selector={config.content_selector}")

        # 创建文章对象（确保总是返回）
        class Article:
            def __init__(self):
                self.title = None
                self.content = None
                self.publish_time = None
                self.author = None
                self.url = url
                self.error = None

        article = Article()
        article.url = url

        try:
            headers = self._get_headers()

            # 获取 HTML（添加重试机制）
            max_retries = 3
            last_error = None

            for attempt in range(max_retries):
                try:
                    response = await self._client.get(url, headers=headers, timeout=30.0)
                    response.raise_for_status()
                    break
                except httpx.HTTPStatusError as e:
                    last_error = e
                    if e.response.status_code == 403:
                        logger.warning(f"403 Forbidden on attempt {attempt + 1}/{max_retries}, retrying with different headers...")
                        await asyncio.sleep(1)
                    elif e.response.status_code == 404:
                        logger.error(f"404 Not Found: {url}")
                        article.error = f"404 Not Found"
                        return article
                    else:
                        raise
                except Exception as e:
                    last_error = e
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
            else:
                raise last_error or Exception("Max retries exceeded")

            # 自动检测编码
            response.encoding = response.encoding or "utf-8"
            html = response.text

            logger.info(f"Fetched HTML length: {len(html)}")

            # 解析 HTML
            soup = BeautifulSoup(html, "lxml")

            # 提取标题
            title = self._extract_text(soup, config.title_selector)
            logger.info(f"Extracted title: {title}")

            # 提取内容
            content = self._extract_content(soup, config.content_selector)
            logger.info(f"Extracted content length: {len(content) if content else 0}")

            # 提取时间 - 优先使用选择器，失败则从完整HTML提取
            publish_time = None
            if config.publish_time_selector:
                time_text = self._extract_text(soup, config.publish_time_selector)
                if time_text:
                    publish_time = self.time_extractor._parse_datetime_string(time_text)
                    if not publish_time:
                        # 如果直接解析失败，尝试从文本中提取
                        publish_time = self.time_extractor._extract_date_from_text(
                            time_text,
                            languages=['zh', 'en', 'ru', 'kk']
                        )

            # 如果选择器未提取到时间，从完整HTML提取
            if not publish_time:
                publish_time = self.time_extractor.extract_publish_time(
                    html_content=html,
                    url=url,
                    languages=['zh', 'en', 'ru', 'kk']
                )
                if publish_time:
                    logger.info(f"Extracted publish_time from HTML: {publish_time}")

            # 提取作者
            author = None
            if config.author_selector:
                author = self._extract_text(soup, config.author_selector)

            # === 智能提取后备：如果内容为空或太短，使用无选择器的智能提取 ===
            if not content or len(content) < 100:
                logger.warning(f"Content too short or empty ({len(content) if content else 0} chars), using SmartExtractor fallback")
                try:
                    smart_extractor = SmartExtractor()
                    smart_result = smart_extractor.extract_all(html, url)

                    # 使用智能提取的结果覆盖（如果更好）
                    if smart_result['title'] and (not title or len(smart_result['title']) > len(title)):
                        title = smart_result['title']
                        logger.info(f"SmartExtractor improved title: {title[:50]}...")

                    if smart_result['content'] and len(smart_result['content']) > 100:
                        content = smart_result['content']
                        logger.info(f"SmartExtractor extracted content: {len(content)} chars")

                    if smart_result['publish_time'] and not publish_time:
                        publish_time = smart_result['publish_time']
                        logger.info(f"SmartExtractor extracted time: {publish_time}")

                except Exception as e:
                    logger.warning(f"SmartExtractor fallback failed: {e}")

            article.title = title
            article.content = content
            article.publish_time = publish_time
            article.author = author

            return article

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {url}: {e}")
            article.error = f"HTTP {e.response.status_code}"
            return article
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}", exc_info=True)
            article.error = str(e)
            return article

    def _extract_text(self, soup: BeautifulSoup, selector: str) -> str | None:
        """提取文本内容"""
        if not selector:
            return None

        # 处理复合选择器 (如 "article, main")
        selectors = [s.strip() for s in selector.split(",")]

        element = None
        for sel in selectors:
            element = soup.select_one(sel)
            if element:
                break

        if not element:
            return None

        text = element.get_text(separator=" ", strip=True)
        return text if text else None

    def _extract_content(self, soup: BeautifulSoup, selector: str) -> str | None:
        """提取正文内容并转换为 Markdown"""
        if not selector:
            return None

        # 处理复合选择器 (如 "article, main")
        selectors = [s.strip() for s in selector.split(",")]

        element = None
        for sel in selectors:
            element = soup.select_one(sel)
            if element:
                break

        if not element:
            return None

        # 使用 html2text 转换为 Markdown
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = False
        h.ignore_emphasis = False
        h.body_width = 0

        html_content = str(element)
        markdown = h.handle(html_content)

        return markdown.strip() if markdown else None
