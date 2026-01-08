"""
联网搜索服务
集成 DuckDuckGo 搜索，提供实时信息补充能力
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class SearchResult:
    """搜索结果项"""

    def __init__(
        self,
        title: str,
        url: str,
        snippet: str,
        published_date: str | None = None,
        source: str | None = None,
    ) -> None:
        self.title = title
        self.url = url
        self.snippet = snippet
        self.published_date = published_date
        self.source = source

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            'title': self.title,
            'url': self.url,
            'snippet': self.snippet,
            'published_date': self.published_date,
            'source': self.source,
        }


class WebSearchEngine:
    """
    联网搜索引擎
    基于 DuckDuckGo (无需 API Key)
    """

    # DuckDuckGo 搜索 API 端点
    DUCKDUCKGO_API = "https://html.duckduckgo.com/html/"

    # 时间范围映射
    TIME_RANGES = {
        'd': 'day',       # 过去一天
        'w': 'week',      # 过去一周
        'm': 'month',     # 过去一月
        'y': 'year',      # 过去一年
    }

    def __init__(
        self,
        timeout: int = 10,
        max_results: int = 10,
        proxy: str | None = None,
    ) -> None:
        """
        初始化搜索引擎

        Args:
            timeout: 请求超时时间（秒）
            max_results: 最大结果数量
            proxy: 代理地址
        """
        self.timeout = timeout
        self.max_results = max_results
        self.proxy = proxy

        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "WebSearchEngine":
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
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                },
            )

    async def _close_client(self) -> None:
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search(
        self,
        query: str,
        time_range: str = 'w',
        max_results: int | None = None,
        region: str = 'us-en',
    ) -> list[SearchResult]:
        """
        执行搜索

        Args:
            query: 搜索关键词
            time_range: 时间范围 ('d'=天, 'w'=周, 'm'=月, 'y'=年)
            max_results: 最大结果数量
            region: 地区设置 (如 'cn-zh', 'kz-kk', 'ru-ru')

        Returns:
            搜索结果列表
        """
        await self._init_client()
        assert self._client is not None

        max_results = max_results or self.max_results

        logger.info(f"Searching: {query} (time_range={time_range})")

        try:
            # 构建搜索参数
            params = {
                'q': query,
                'kl': region,
            }

            # 添加时间范围（通过搜索关键词）
            if time_range in self.TIME_RANGES:
                range_name = self.TIME_RANGES[time_range]
                # DuckDuckGo 通过特殊语法实现时间过滤
                # 例如：query + " site:duckduckgo.com" 有不同的效果
                # 这里使用简单的方法
                params['df'] = range_name

            # 发送请求
            response = await self._client.get(
                self.DUCKDUCKGO_API,
                params=params,
            )
            response.raise_for_status()

            # 解析结果
            results = self._parse_html_results(response.text, max_results)

            logger.info(f"Found {len(results)} results")

            return results

        except httpx.HTTPError as e:
            logger.error(f"Search failed: {e}")
            return []

    def _parse_html_results(self, html: str, max_results: int) -> list[SearchResult]:
        """
        解析 DuckDuckGo HTML 结果
        """
        results: list[SearchResult] = []

        soup = BeautifulSoup(html, 'html.parser')

        # DuckDuckGo 的结果在 .result 类中
        result_divs = soup.select('.result')

        for div in result_divs[:max_results]:
            try:
                # 提取标题和链接
                title_elem = div.select_one('.result__title a')
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                url = title_elem.get('href', '')

                # 提取摘要
                snippet_elem = div.select_one('.result__snippet')
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''

                # 提取来源
                source_elem = div.select_one('.result__url')
                source = source_elem.get_text(strip=True) if source_elem else None

                results.append(SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source=source,
                ))

            except Exception as e:
                logger.debug(f"Failed to parse result: {e}")
                continue

        return results

    async def fetch_page_content(self, url: str, max_length: int = 5000) -> str | None:
        """
        获取网页内容
        用于补充上下文

        Args:
            url: 目标 URL
            max_length: 最大内容长度

        Returns:
            网页文本内容
        """
        await self._init_client()
        assert self._client is not None

        try:
            response = await self._client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # 移除脚本和样式
            for script in soup(['script', 'style']):
                script.decompose()

            # 获取文本
            text = soup.get_text(separator='\n', strip=True)

            # 限制长度
            if len(text) > max_length:
                text = text[:max_length] + '...'

            return text

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None


class ContextEnricher:
    """
    上下文增强器（优化版）
    负责将搜索结果与本地数据融合
    支持时间优先的合并逻辑
    """

    def __init__(
        self,
        search_engine: WebSearchEngine | None = None,
    ) -> None:
        """
        初始化增强器

        Args:
            search_engine: 搜索引擎实例
        """
        self.search_engine = search_engine or WebSearchEngine()

    async def enrich_with_search(
        self,
        query: str,
        local_articles: list[dict[str, Any]],
        time_range: str = 'w',
        max_external_results: int = 5,
    ) -> dict[str, Any]:
        """
        使用搜索结果增强本地数据
        支持时间优先的合并逻辑

        Args:
            query: 搜索关键词
            local_articles: 本地文章列表
            time_range: 时间范围
            max_external_results: 最大外部结果数量

        Returns:
            增强后的上下文
        """
        enrichment = {
            'local_count': len(local_articles),
            'external_results': [],
            'merged_articles': [],
            'conflicts_resolved': 0,
            'combined_context': '',
        }

        # 执行搜索
        external_results = await self.search_engine.search(
            query=query,
            time_range=time_range,
            max_results=max_external_results,
        )

        enrichment['external_count'] = len(external_results)
        enrichment['external_results'] = [r.to_dict() for r in external_results]

        # 时间优先合并
        merged_articles = self._merge_with_time_priority(local_articles, external_results)
        enrichment['merged_articles'] = merged_articles

        # 统计冲突解决数量
        enrichment['conflicts_resolved'] = self._count_conflicts(local_articles, external_results)

        # 组合上下文
        combined = self._combine_contexts_time_priority(merged_articles)
        enrichment['combined_context'] = combined

        return enrichment

    def _merge_with_time_priority(
        self,
        local_articles: list[dict[str, Any]],
        external_results: list[SearchResult],
    ) -> list[dict[str, Any]]:
        """
        时间优先合并逻辑
        当联网搜索与本地文章内容冲突时，优先使用更新的信息

        Args:
            local_articles: 本地文章列表
            external_results: 外部搜索结果

        Returns:
            合并后的文章列表
        """
        # 按时间排序本地文章
        local_with_time = []
        for article in local_articles:
            pub_time = article.get('publish_time') or article.get('created_at')
            # 如果是字符串格式，转换为 datetime 对象
            if isinstance(pub_time, str):
                try:
                    pub_time = datetime.fromisoformat(pub_time.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pub_time = None
            local_with_time.append({
                'article': article,
                'publish_time': pub_time,
                'source': 'local',
                'timestamp': pub_time.timestamp() if pub_time else 0,
            })

        # 按时间排序外部结果
        external_with_time = []
        for result in external_results:
            # 尝试解析发布日期
            pub_time = self._parse_publish_date(result.published_date)
            external_with_time.append({
                'article': result.to_dict(),
                'publish_time': pub_time,
                'source': 'external',
                'timestamp': pub_time.timestamp() if pub_time else 0,
            })

        # 合并并按时间排序
        all_articles = local_with_time + external_with_time
        all_articles.sort(key=lambda x: x['timestamp'], reverse=True)

        # 去重（基于标题相似度）
        seen_titles = set()
        unique_articles = []

        for item in all_articles:
            article = item['article']
            title = article.get('title', '')
            normalized_title = self._normalize_title(title)

            if normalized_title not in seen_titles:
                seen_titles.add(normalized_title)
                unique_articles.append(article)

        return unique_articles

    @staticmethod
    def _normalize_title(title: str) -> str:
        """标准化标题用于去重"""
        if not title:
            return ''
        # 转小写
        title = title.lower()
        # 移除特殊字符
        for char in '，。！？、；：""''《》【】(),.!?;:"''—–':
            title = title.replace(char, '')
        # 移除空格
        title = title.replace(' ', '')
        return title

    @staticmethod
    def _parse_publish_date(date_str: str | None) -> datetime | None:
        """
        解析发布日期
        支持多种格式
        """
        if not date_str:
            return None

        from datetime import timedelta

        now = datetime.now(timezone.utc)

        # 相对时间
        if '小时前' in date_str:
            hours = int(date_str.replace('小时前', '').strip())
            return now - timedelta(hours=hours)
        elif '天前' in date_str:
            days = int(date_str.replace('天前', '').strip())
            return now - timedelta(days=days)
        elif 'ago' in date_str:
            parts = date_str.split()
            if len(parts) >= 2:
                if 'hour' in parts[1]:
                    hours = int(parts[0])
                    return now - timedelta(hours=hours)
                elif 'day' in parts[1]:
                    days = int(parts[0])
                    return now - timedelta(days=days)

        # ISO 格式 (优先处理，更高效)
        try:
            # 处理标准 ISO 格式：2025-01-01T12:00:00 或 2025-01-01T12:00:00Z
            cleaned = date_str.replace('Z', '+00:00')
            parsed = datetime.fromisoformat(cleaned)
            # 如果解析出的 datetime 没有时区，添加 UTC 时区
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except (ValueError, AttributeError):
            pass

        # 尝试 dateparser 作为备用
        try:
            from dateparser import parse
            parsed = parse(date_str)
            if parsed:
                # 确保返回带时区的 datetime
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
        except Exception:
            pass

        return None

    def _count_conflicts(
        self,
        local_articles: list[dict[str, Any]],
        external_results: list[SearchResult],
    ) -> int:
        """
        统计冲突数量
        即：同一事件，本地是旧数据，外部是新数据
        """
        conflicts = 0

        # 创建本地标题集合
        local_titles = set()
        for article in local_articles:
            title = article.get('title', '')
            local_titles.add(self._normalize_title(title))

        # 检查外部结果
        for result in external_results:
            title = result.title
            normalized = self._normalize_title(title)

            if normalized in local_titles:
                # 检查时间差异
                local_time = self._get_newest_time(local_articles)
                external_time = self._parse_publish_date(result.published_date)

                if local_time and external_time:
                    time_diff = (external_time - local_time).total_seconds()
                    # 如果外部更新超过 1 小时，认为是冲突
                    if time_diff > 3600:
                        conflicts += 1

        return conflicts

    def _get_newest_time(self, articles: list[dict[str, Any]]) -> datetime | None:
        """获取文章列表中最新的时间"""
        newest = None
        for article in articles:
            pub_time = article.get('publish_time') or article.get('created_at')
            if pub_time:
                if newest is None or pub_time > newest:
                    newest = pub_time
        return newest

    def _combine_contexts_time_priority(
        self,
        merged_articles: list[dict[str, Any]],
    ) -> str:
        """
        组合上下文（时间优先）
        """
        sections = []

        # 按时间分组
        now = datetime.now(timezone.utc)
        very_recent = []  # 24 小时内
        recent = []  # 一周内
        older = []  # 更早

        for article in merged_articles:
            # 尝试获取发布时间
            pub_time = None

            if 'publish_time' in article:
                raw_pub_time = article['publish_time']
                # 处理不同类型的 publish_time
                if isinstance(raw_pub_time, datetime):
                    pub_time = raw_pub_time
                elif isinstance(raw_pub_time, str):
                    pub_time = self._parse_publish_date(raw_pub_time)
            elif 'published_date' in article:
                pub_time = self._parse_publish_date(article.get('published_date'))

            if not pub_time:
                older.append(article)
                continue

            # 统一时区处理：确保两个 datetime 对象时区一致
            if pub_time.tzinfo is None:
                # pub_time 是 naive，视为 UTC
                pub_time_naive = pub_time
                now_naive = now.replace(tzinfo=None)
            else:
                # pub_time 是 aware，转换为 UTC 后去掉时区
                pub_time_utc = pub_time.astimezone(timezone.utc)
                pub_time_naive = pub_time_utc.replace(tzinfo=None)
                now_naive = now.replace(tzinfo=None)

            age_hours = (now_naive - pub_time_naive).total_seconds()

            if age_hours < 24:
                very_recent.append(article)
            elif age_hours < 168:
                recent.append(article)
            else:
                older.append(article)

        # 按时间顺序输出
        if very_recent:
            sections.append("## 最新动态（24小时内）\n")
            for article in very_recent[:5]:
                title = article.get('title', 'Untitled')
                sections.append(f"- {title}\n")

        if recent:
            sections.append("\n## 本周动态\n")
            for article in recent[:5]:
                title = article.get('title', 'Untitled')
                sections.append(f"- {title}\n")

        if older and len(merged_articles) > 10:
            sections.append("\n## 历史参考\n")
            for article in older[:3]:
                title = article.get('title', 'Untitled')
                sections.append(f"- {title}\n")

        return '\n'.join(sections)

    async def search_and_fetch(
        self,
        query: str,
        time_range: str = 'w',
        fetch_content: bool = True,
        max_results: int = 3,
    ) -> list[dict[str, Any]]:
        """
        搜索并获取完整内容
        用于深度背景补充

        Args:
            query: 搜索关键词
            time_range: 时间范围
            fetch_content: 是否获取完整内容
            max_results: 最大结果数

        Returns:
            包含完整内容的搜索结果
        """
        results = await self.search_engine.search(
            query=query,
            time_range=time_range,
            max_results=max_results,
        )

        if not fetch_content:
            return [r.to_dict() for r in results]

        # 并发获取内容
        tasks = [
            self.search_engine.fetch_page_content(r.url)
            for r in results
        ]

        contents = await asyncio.gather(*tasks)

        enriched_results = []
        for result, content in zip(results, contents):
            data = result.to_dict()
            if content:
                data['full_content'] = content
            enriched_results.append(data)

        return enriched_results

    async def close(self) -> None:
        """关闭资源"""
        await self.search_engine._close_client()


# 便捷函数
async def quick_search(
    query: str,
    time_range: str = 'w',
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """
    快速搜索

    Args:
        query: 搜索关键词
        time_range: 时间范围
        max_results: 最大结果数

    Returns:
        搜索结果列表
    """
    async with WebSearchEngine() as engine:
        results = await engine.search(
            query=query,
            time_range=time_range,
            max_results=max_results,
        )
        return [r.to_dict() for r in results]
