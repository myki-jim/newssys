"""
时间提取引擎
使用确定性规则算法从 HTML 中提取发布时间
不依赖 AI，完全基于规则匹配
"""

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import dateparser
from lxml import etree


class TimeExtractor:
    """
    时间提取引擎
    按优先级依次尝试多种方法提取发布时间
    """

    # 多语言"发布日期"关键词映射
    DATE_KEYWORDS = {
        "zh": [
            "发布时间", "发布日期", "发表时间", "发表日期",
            "时间", "日期", "上传时间", "更新时间",
            "出处", "来源", "转载于",
        ],
        "ru": [
            "Опубликовано", "дата публикации", "опубликовано",
            "обновлено", "дата", "время",
            "Добавлено", "Создано",
        ],
        "kk": [
            "Жарияланған", "Жариялану уақыты", "жарияланды",
            "жаңартылды", "күні", "уақыты",
            "Қосылған", "Жасалған",
        ],
        "en": [
            "Published", "Publish date", "Date published",
            "Updated", "Last updated", "Post date",
            "Posted", "Created", "Author",
        ],
    }

    # Meta 标签选择器
    META_SELECTORS = [
        # Open Graph
        'meta[property="article:published_time"]',
        'meta[property="article:modified_time"]',
        'meta[property="og:published_time"]',
        'meta[property="og:updated_time"]',
        # Schema.org
        'meta[itemprop="datePublished"]',
        'meta[itemprop="dateModified"]',
        # Twitter
        'meta[name="twitter:created_at"]',
        # 标准 meta
        'meta[name="pubdate"]',
        'meta[name="publish_date"]',
        'meta[name="date"]',
        'meta[name="article:published"]',
        'meta[name="article:published_time"]',
        # Dublin Core
        'meta[name="DC.date"]',
        'meta[name="DC.date.created"]',
        'meta[name="DC.date.issued"]',
    ]

    # URL 日期正则模式
    URL_DATE_PATTERNS = [
        # 标准格式: /2024/05/20/ 或 /2024-05-20/
        r'/(\d{4})[/-](\d{2})[/-](\d{2})/',
        # 紧凑格式: /20240520/
        r'/(\d{4})(\d{2})(\d{2})/',
        # 年月格式: /2024/05/
        r'/(\d{4})[/-](\d{2})/',
        # 中文新闻站点: /2024/0520/
        r'/(\d{4})[/-](\d{4})/',
        # 俄文/哈文新闻站点常见: /20/05/2024/
        r'/(\d{2})[/-](\d{2})[/-](\d{4})/',
    ]

    def __init__(self, default_timezone: str | None = None) -> None:
        """
        初始化时间提取器

        Args:
            default_timezone: 默认时区（如 'Asia/Shanghai'）
        """
        self.default_timezone = default_timezone
        self._setup_dateparser_settings()

    def _setup_dateparser_settings(self) -> None:
        """配置 dateparser 设置"""
        self.dateparser_settings = {
            'TIMEZONE': self.default_timezone or 'UTC',
            'RETURN_AS_TIMEZONE_AWARE': True,
            'RELATIVE_BASE': datetime.now(timezone.utc),
        }

    def extract_publish_time(
        self,
        html_content: str,
        url: str,
        languages: list[str] | None = None,
    ) -> datetime | None:
        """
        提取发布时间
        按优先级依次尝试多种方法

        Args:
            html_content: HTML 内容
            url: 页面 URL
            languages: 语言列表（默认 ['zh', 'ru', 'kk', 'en']）

        Returns:
            datetime 对象，提取失败返回 None
        """
        if languages is None:
            languages = ['zh', 'ru', 'kk', 'en']

        # 1. 尝试从 JSON-LD 提取
        dt = self._extract_from_json_ld(html_content)
        if dt:
            return dt

        # 2. 尝试从 Meta 标签提取
        dt = self._extract_from_meta_tags(html_content)
        if dt:
            return dt

        # 3. 尝试从 URL 提取
        dt = self._extract_from_url(url)
        if dt:
            return dt

        # 4. 尝试从 HTML 文本提取（多语言关键词）
        dt = self._extract_from_html_text(html_content, languages)
        if dt:
            return dt

        return None

    def _extract_from_json_ld(self, html_content: str) -> datetime | None:
        """
        从 JSON-LD 提取时间
        优先级最高
        """
        soup = BeautifulSoup(html_content, 'lxml')

        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string or '{}')
                # 处理多种可能的 JSON-LD 结构
                time_fields = self._extract_time_from_jsonld_data(data)
                if time_fields:
                    for time_str in time_fields:
                        dt = self._parse_datetime_string(time_str)
                        if dt:
                            return dt
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue

        return None

    def _extract_time_from_jsonld_data(self, data: Any, max_depth: int = 5) -> list[str] | None:
        """
        递归从 JSON-LD 数据中提取时间字段
        """
        if max_depth <= 0:
            return None

        time_fields = []

        # 如果是字典，查找时间相关字段
        if isinstance(data, dict):
            # 直接查找日期字段
            for key in ['datePublished', 'dateModified', 'dateCreated', 'publishDate',
                        'uploadDate', 'date', 'publishedDate', 'publicationDate']:
                value = data.get(key)
                if value and isinstance(value, str):
                    time_fields.append(value)

            # 递归查找嵌套对象
            for value in data.values():
                result = self._extract_time_from_jsonld_data(value, max_depth - 1)
                if result:
                    time_fields.extend(result)

        # 如果是列表，递归处理每个元素
        elif isinstance(data, list):
            for item in data:
                result = self._extract_time_from_jsonld_data(item, max_depth - 1)
                if result:
                    time_fields.extend(result)

        return time_fields if time_fields else None

    def _extract_from_meta_tags(self, html_content: str) -> datetime | None:
        """
        从 Meta 标签提取时间
        优先级第二
        """
        soup = BeautifulSoup(html_content, 'lxml')

        for selector in self.META_SELECTORS:
            meta = soup.select_one(selector)
            if meta:
                content = meta.get('content')
                if content:
                    dt = self._parse_datetime_string(content)
                    if dt:
                        return dt

        return None

    def _extract_from_url(self, url: str) -> datetime | None:
        """
        从 URL 提取日期
        优先级第三
        """
        parsed = urlparse(url)
        path = parsed.path

        for pattern in self.URL_DATE_PATTERNS:
            match = re.search(pattern, path)
            if match:
                groups = match.groups()
                try:
                    if len(groups) == 3:
                        # 年月日
                        y, m, d = groups
                        if len(y) == 2 and len(d) == 4:
                            # 处理 /20/05/2024/ 格式
                            y, d = d, y
                        return datetime(int(y), int(m), int(d))
                    elif len(groups) == 2:
                        # 年月
                        y, m = groups
                        return datetime(int(y), int(m), 1)
                except (ValueError, IndexError):
                    continue

        return None

    def _extract_from_html_text(
        self,
        html_content: str,
        languages: list[str],
    ) -> datetime | None:
        """
        从 HTML 文本提取时间
        基于多语言关键词匹配
        优先级第四
        """
        soup = BeautifulSoup(html_content, 'lxml')

        for lang in languages:
            keywords = self.DATE_KEYWORDS.get(lang, [])
            for keyword in keywords:
                # 查找包含关键词的元素
                candidates = self._find_elements_with_keyword(soup, keyword)

                for candidate in candidates:
                    # 从候选元素中提取日期
                    text = candidate.get_text(strip=True)
                    dt = self._extract_date_from_text(text, languages=[lang, 'en'])
                    if dt:
                        return dt

        # 如果关键词方法失败，尝试全局搜索日期模式
        return self._extract_date_from_text(html_content, languages)

    def _find_elements_with_keyword(self, soup: BeautifulSoup, keyword: str) -> list:
        """
        查找包含关键词的元素
        """
        candidates = []

        # 查找包含关键词的文本节点
        for element in soup.find_all(['time', 'span', 'div', 'p', 'small', 'td']):
            text = element.get_text(strip=True)
            if keyword in text:
                candidates.append(element)

        # 查找包含关键词的 datetime 属性
        time_elements = soup.find_all('time', attrs={'datetime': True})
        for time_el in time_elements:
            candidates.append(time_el)

        return candidates

    def _extract_date_from_text(
        self,
        text: str,
        languages: list[str],
    ) -> datetime | None:
        """
        从文本中提取日期
        使用 dateparser 处理多语言日期
        """
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text).strip()

        # 通用日期模式（ISO 8601 格式）
        iso_patterns = [
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',
            r'\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}',
            r'\d{4}-\d{2}-\d{2}',
        ]

        for pattern in iso_patterns:
            match = re.search(pattern, text)
            if match:
                dt = self._parse_datetime_string(match.group())
                if dt:
                    return dt

        # 使用 dateparser 解析自然语言日期
        for lang in languages:
            try:
                dt = dateparser.parse(
                    text,
                    settings={
                        **self.dateparser_settings,
                        'LANGUAGES': [lang],
                    }
                )
                if dt:
                    # 确保返回带时区的 datetime
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
            except (AttributeError, ValueError, TypeError):
                continue

        return None

    def _parse_datetime_string(self, datetime_str: str) -> datetime | None:
        """
        解析日期时间字符串
        支持多种常见格式
        """
        if not datetime_str:
            return None

        # 尝试直接解析 ISO 格式
        iso_formats = [
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%d.%m.%Y',
            '%d/%m/%Y',
        ]

        for fmt in iso_formats:
            try:
                dt = datetime.strptime(datetime_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue

        # 使用 dateparser 作为后备
        try:
            dt = dateparser.parse(datetime_str, settings=self.dateparser_settings)
            if dt:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
        except (AttributeError, ValueError):
            pass

        return None

    def extract_raw_time_text(
        self,
        html_content: str,
        selector: str | None = None,
    ) -> str | None:
        """
        提取原始时间文本
        用于调试和日志记录

        Args:
            html_content: HTML 内容
            selector: CSS 选择器（可选）

        Returns:
            原始时间文本
        """
        if selector:
            soup = BeautifulSoup(html_content, 'lxml')
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True) or element.get('datetime')

        # 如果没有提供选择器，尝试自动查找
        dt = self._extract_from_meta_tags(html_content)
        if dt:
            return dt.isoformat()

        return None


# 多语言月份名称映射（用于 dateparser 无法处理的情况）
MULTILINGUAL_MONTHS = {
    # 哈萨克语
    'қаңтар': 1, 'ақпан': 2, 'наурыз': 3, 'сәуір': 4, 'мамыр': 5,
    'маусым': 6, 'шіле': 7, 'тамыз': 8, 'қыркүйек': 9, 'қазан': 10,
    'қараша': 11, 'желтоқсан': 12,
    # 俄语
    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5,
    'июня': 6, 'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10,
    'ноября': 11, 'декабря': 12,
    'январь': 1, 'февраль': 2, 'март': 3, 'апрель': 4, 'май': 5,
    'июнь': 6, 'июль': 7, 'август': 8, 'сентябрь': 9, 'октябрь': 10,
    'ноябрь': 11, 'декабрь': 12,
}
