"""
智能内容提取器
不依赖CSS选择器，使用启发式算法从网页中提取：
1. 纯文本内容（自动去除导航、侧边栏、页脚等噪音）
2. 标题
3. 发布时间（使用大量正则规则）
"""

import re
import logging
from datetime import datetime, timezone
from typing import Optional
from bs4 import BeautifulSoup, Tag

from src.services.time_extractor import TimeExtractor

logger = logging.getLogger(__name__)


class SmartExtractor:
    """
    智能网页内容提取器
    使用纯启发式算法，不依赖任何CSS选择器
    """

    # 短文本阈值（字符数小于此值认为是噪音）
    MIN_TEXT_LENGTH = 50

    # 需要移除的噪音元素（class/id关键词）
    NOISE_PATTERNS = [
        r'\bnav\b', r'\bnavigation\b', r'\bmenu\b', r'\bheader\b', r'\bfooter\b',
        r'\bsidebar\b', r'\bside-bar\b', r'\bwidget\b', r'\bbanner\b', r'\bad\b',
        r'\bcomment\b', r'\bcomments\b', r'\bshare\b', r'\bbutton\b', r'\bbtn\b',
        r'\bsubscribe\b', r'\bfollow\b', r'\blike\b', r'\bsocial\b',
        r'\brelated\b', r'\brecommend\b', r'\bpopular\b', r'\btrending\b',
        r'\btag\b', r'\bcategory\b', r'\bauthor-info\b', r'\bbreadcrumb\b',
        r'\badvertisement\b', r'\bsponsored\b', r'\bpromo\b',
    ]

    def __init__(self):
        """初始化智能提取器"""
        self.time_extractor = TimeExtractor(default_timezone='UTC')

    def extract_all(self, html: str, url: str) -> dict:
        """
        从HTML中提取所有信息

        Args:
            html: HTML内容
            url: 页面URL

        Returns:
            包含 title, content, publish_time 的字典
        """
        try:
            soup = BeautifulSoup(html, 'lxml')

            # 移除脚本和样式
            for element in soup(['script', 'style', 'noscript', 'iframe', 'svg']):
                element.decompose()

            # 提取标题
            title = self._extract_title(soup)

            # 提取内容
            content = self._extract_content(soup)

            # 提取时间（使用多种规则）
            publish_time = self._extract_time(html, url, soup)

            return {
                'title': title,
                'content': content,
                'publish_time': publish_time,
            }
        except Exception as e:
            logger.error(f"SmartExtractor.extract_all failed: {e}")
            return {
                'title': None,
                'content': None,
                'publish_time': None,
            }

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """提取标题（按优先级）"""
        # 1. h1 标签
        h1 = soup.find('h1')
        if h1:
            title = self._clean_text(h1.get_text())
            if title and len(title) > 5 and len(title) < 200:
                return title

        # 2. title 标签
        title_tag = soup.find('title')
        if title_tag:
            title = self._clean_text(title_tag.get_text())
            title = re.sub(r'\s*[-_|–:]\s*(.*)$', '', title)
            if title and len(title) > 5:
                return title

        # 3. meta og:title
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            if meta.get('property') == 'og:title' or meta.get('name') == 'og:title':
                content = meta.get('content')
                if content:
                    title = self._clean_text(content)
                    if title and len(title) > 5:
                        return title

        # 4. h2-h6
        for tag_name in ['h2', 'h3', 'h4', 'h5', 'h6']:
            tag = soup.find(tag_name)
            if tag:
                title = self._clean_text(tag.get_text())
                if title and len(title) > 10:
                    return title

        return None

    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        """提取正文内容"""
        try:
            # 1. article 或 main 标签
            for tag_name in ['article', 'main']:
                element = soup.find(tag_name)
                if element:
                    content = self._get_text_from_element(element)
                    if content and len(content) > self.MIN_TEXT_LENGTH:
                        return content

            # 2. 找最大的div
            best_content = None
            best_length = 0

            for div in soup.find_all('div', limit=100):  # 限制数量避免太慢
                if self._is_noise(div):
                    continue

                content = self._get_text_from_element(div)
                if content and len(content) > best_length and len(content) > self.MIN_TEXT_LENGTH:
                    best_length = len(content)
                    best_content = content

            if best_content:
                return best_content

            # 3. 所有段落
            paragraphs = soup.find_all('p', limit=50)
            texts = []
            for p in paragraphs:
                text = self._clean_text(p.get_text())
                if text and len(text) > 20:
                    texts.append(text)

            if texts:
                return ' '.join(texts)

            return None
        except Exception as e:
            logger.warning(f"_extract_content failed: {e}")
            return None

    def _get_text_from_element(self, element: Tag) -> Optional[str]:
        """从元素中提取纯文本"""
        try:
            # 移除噪音子元素
            for child in element.find_all(True):
                if self._is_noise(child):
                    child.decompose()

            # 提取文本
            texts = []
            for tag in element.find_all(['p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'td']):
                text = self._clean_text(tag.get_text())
                if text and len(text) > 10:
                    texts.append(text)

            if texts:
                return ' '.join(texts)

            # 直接提取
            text = self._clean_text(element.get_text())
            return text if text else None
        except Exception:
            return None

    def _is_noise(self, element: Tag) -> bool:
        """判断元素是否为噪音"""
        try:
            if not element:
                return False

            classes = element.get('class') or []
            elem_id = element.get('id') or ''

            combined = ' '.join(classes) + ' ' + elem_id
            combined = combined.lower()

            for pattern in self.NOISE_PATTERNS:
                if re.search(pattern, combined):
                    return True

            return False
        except Exception:
            return False

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ''

        # 合并空白
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        # 过滤无效内容
        invalid_patterns = [
            r'^\s*(点击查看更多|more|continue|read)\s*$',
            r'^\s*javascript\s*required',
            r'^\s*[请启用|请开启|enable].*javascript',
        ]

        for pattern in invalid_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return ''

        return text

    def _extract_time(self, html: str, url: str, soup: BeautifulSoup) -> Optional[datetime]:
        """提取发布时间"""
        try:
            # 使用 TimeExtractor
            dt = self.time_extractor.extract_publish_time(html, url)
            if dt:
                return dt
        except Exception:
            pass

        # 简单的后备方案：从URL提取
        try:
            url_patterns = [
                r'/(\d{4})/(\d{2})/(\d{2})/',
                r'/(\d{4})-(\d{2})-(\d{2})/',
            ]
            for pattern in url_patterns:
                match = re.search(pattern, url)
                if match:
                    try:
                        y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
                        if 2000 < y < 2100:
                            return datetime(y, m, d, tzinfo=timezone.utc)
                    except ValueError:
                        pass
        except Exception:
            pass

        return None
