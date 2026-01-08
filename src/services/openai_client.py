"""
OpenAI API 客户端
支持流式响应和关键词生成
"""

import asyncio
import logging
import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from src.core.config import settings


logger = logging.getLogger(__name__)


class OpenAIClient:
    """OpenAI API 客户端"""

    def __init__(self) -> None:
        self.base_url = settings.ai.base_url
        self.api_key = settings.ai.api_key
        self.model = settings.ai.model
        self.max_tokens = settings.ai.max_tokens
        self.temperature = settings.ai.temperature
        self.timeout = settings.ai.timeout

    async def _stream_chat(
        self,
        messages: list[dict[str, str]],
    ) -> AsyncGenerator[str, None]:
        """
        流式聊天

        Args:
            messages: 消息列表

        Yields:
            响应文本片段
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": True,
        }

        last_activity = None
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout, connect=10.0),
                ) as client:
                    async with client.stream(
                        "POST",
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=payload,
                    ) as response:
                        if response.status_code != 200:
                            error_text = await response.aread()
                            logger.error(f"OpenAI API error: {response.status_code} - {error_text}")
                            raise Exception(f"AI API error: {response.status_code}")

                        # 流式读取响应
                        async for line in response.aiter_lines():
                            if not line.strip():
                                continue

                            if line.startswith("data: "):
                                data_str = line[6:]  # 移除 "data: " 前缀

                                if data_str == "[DONE]":
                                    break

                                try:
                                    data = json.loads(data_str)
                                    content = data.get("choices", [{}])[0].get("delta", {}).get("content")
                                    if content:
                                        last_activity = True  # 有活动
                                        yield content
                                except json.JSONDecodeError as e:
                                    logger.warning(f"Failed to parse SSE data: {e}")
                                    continue

                        # 正常完成，退出重试循环
                        break

            except httpx.TimeoutException as e:
                retry_count += 1
                logger.warning(f"AI API timeout (attempt {retry_count}/{max_retries}): {e}")
                if retry_count >= max_retries:
                    raise Exception(f"AI API 超时，已重试 {max_retries} 次")
                # 等待后重试
                await asyncio.sleep(2)

            except httpx.ConnectError as e:
                retry_count += 1
                logger.warning(f"AI API connection error (attempt {retry_count}/{max_retries}): {e}")
                if retry_count >= max_retries:
                    raise Exception(f"AI API 连接失败，已重试 {max_retries} 次")
                await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"AI API error: {e}")
                raise

    async def chat(
        self,
        user_message: str,
        system_prompt: str | None = None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        聊天（流式）

        Args:
            user_message: 用户消息
            system_prompt: 系统提示词
            conversation_history: 对话历史

        Yields:
            响应文本片段
        """
        messages = []

        # 添加系统提示词
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 添加对话历史
        if conversation_history:
            # 只保留最近的几轮对话
            recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
            messages.extend(recent_history)

        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        # 流式生成响应
        async for chunk in self._stream_chat(messages):
            yield chunk

    async def generate_keywords(
        self,
        query: str,
        max_keywords: int = 3,
    ) -> list[str]:
        """
        生成搜索关键词

        Args:
            query: 用户查询
            max_keywords: 最大关键词数量

        Returns:
            关键词列表
        """
        system_prompt = f"""你是一个搜索关键词生成助手。根据用户的查询，生成 {max_keywords} 个最相关的搜索关键词。

规则：
1. 关键词应该简洁、准确
2. 包含中文关键词
3. 如果是新闻类查询，包含英文关键词
4. 只返回关键词列表，格式如：["关键词1", "关键词2", "关键词3"]
5. 不要有其他解释文字
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"用户查询：{query}\n\n请生成搜索关键词："},
        ]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 200,
            "temperature": 0.7,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )

                if response.status_code != 200:
                    logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                    # 返回默认关键词
                    return self._default_keywords(query, max_keywords)

                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                # 解析关键词
                keywords = self._parse_keywords(content)
                return keywords[:max_keywords] if keywords else self._default_keywords(query, max_keywords)

        except Exception as e:
            logger.error(f"Failed to generate keywords: {e}")
            return self._default_keywords(query, max_keywords)

    def _parse_keywords(self, content: str) -> list[str]:
        """解析关键词"""
        content = content.strip()

        # 尝试解析 JSON 数组
        if content.startswith("["):
            try:
                keywords = json.loads(content)
                if isinstance(keywords, list):
                    return [k.strip() for k in keywords if k.strip()]
            except json.JSONDecodeError:
                pass

        # 解析逗号分隔的关键词
        # 去除引号和中英文标点符号
        import string
        punctuations = string.punctuation + "（）()[]【】""''「」『』"
        keywords = [k.strip(punctuations).strip() for k in content.split(",")]
        return [k for k in keywords if k and len(k) > 1]

    def _default_keywords(self, query: str, max_keywords: int = 3) -> list[str]:
        """生成默认关键词"""
        keywords = []

        # 使用查询本身作为第一个关键词
        if query:
            keywords.append(query[:50])  # 限制长度

        # 提取查询中的名词性词语（简单实现）
        if len(query) > 5:
            keywords.append(query[:20] + "相关")

        if len(keywords) < max_keywords:
            keywords.append("最新消息")

        return keywords[:max_keywords]

    def build_search_context(
        self,
        keywords: list[str],
        internal_results: list[dict[str, Any]],
        web_results: list[dict[str, Any]],
    ) -> str:
        """构建搜索结果上下文"""
        context_parts = []

        # 添加关键词信息
        context_parts.append(f"搜索关键词：{', '.join(keywords)}\n")

        # 添加内部搜索结果
        if internal_results:
            context_parts.append("\n=== 内部知识库结果 ===")
            for i, result in enumerate(internal_results[:5], 1):
                context_parts.append(f"\n{i}. {result.get('title', '无标题')}")
                context_parts.append(f"   时间: {result.get('publish_time', '未知')}")
                context_parts.append(f"   链接: {result.get('url', '')}")
                content = result.get('content') or result.get('snippet') or ''
                if content:
                    content_str = str(content)[:300] if not isinstance(content, str) else content[:300]
                    context_parts.append(f"   内容: {content_str}...")

        # 添加联网搜索结果
        if web_results:
            context_parts.append("\n=== 联网搜索结果 ===")
            for i, result in enumerate(web_results[:5], 1):
                context_parts.append(f"\n{i}. {result.get('title', '无标题')}")
                context_parts.append(f"   时间: {result.get('publish_time', '未知')}")
                context_parts.append(f"   链接: {result.get('url', '')}")
                content = result.get('content') or result.get('snippet') or ''
                if content:
                    content_str = str(content)[:300] if not isinstance(content, str) else content[:300]
                    context_parts.append(f"   内容: {content_str}...")

        return "\n".join(context_parts)


# 全局实例
_openai_client: OpenAIClient | None = None


def get_openai_client() -> OpenAIClient:
    """获取 OpenAI 客户端实例"""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAIClient()
    return _openai_client
