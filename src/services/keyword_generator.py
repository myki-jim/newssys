"""
AI 关键字生成服务
根据报告标题、时间范围、用户输入等信息生成关键字列表
"""

import logging
from datetime import datetime
from typing import Any

from src.services.openai_client import get_openai_client


logger = logging.getLogger(__name__)


class KeywordGenerator:
    """AI 关键字生成器"""

    def __init__(self):
        self.ai_client = get_openai_client()

    async def generate_keywords(
        self,
        title: str,
        time_start: datetime,
        time_end: datetime,
        user_prompt: str | None = None,
        language: str = "zh",
        max_keywords: int = 10,
    ) -> list[str]:
        """
        使用 AI 生成报告关键字

        Args:
            title: 报告标题
            time_start: 时间范围开始
            time_end: 时间范围结束
            user_prompt: 用户自定义要求
            language: 语言（zh=中文, kk=哈萨克语）
            max_keywords: 最大关键字数量

        Returns:
            关键字列表（包含中文和哈萨克语）
        """
        # 计算时间跨度
        time_delta = (time_end - time_start).days
        if time_delta <= 7:
            time_range_desc = "本周"
        elif time_delta <= 14:
            time_range_desc = "最近两周"
        elif time_delta <= 31:
            time_range_desc = "本月"
        elif time_delta <= 90:
            time_range_desc = "本季度"
        else:
            time_range_desc = f"最近{time_delta // 30}个月"

        # 根据语言设置不同的提示词
        if language == "kk":
            system_prompt = f"""Сен сіз кәсібижілік сарапатымын тірекеш сөздерін шығаруға маманданыңыз.

Келесі ережелерді сақтаңыз:
1. {max_keywords} маңызды ең маңызды тірекеш сөздерді шығарыңыз
2. Тірекеш сөздер қысқа және нақты болуы керек, әдетте 2-4 сөзден тұратын зат есімдер немесе біріктер
3. Адамдар аты, жерлер аты, ұйымдар аты, оқиғалар аты сияқты аттарды басымдыққа
4. Тірекеш сөздер есептің негізгі тақырыбын сипаттай алуы тиіс
5. Маңыздылығы қарай сұрыпталған
6. Тек тірекеш сөздер тізімін қайтарыңыз, үтірлер арқылы бөліңіз, басқа ақпарат болмаңыз

Мысалдар:
Кіріс: Венесуэла жаңылығы, президент Мадуроның мұнай саясатына назар аудару
Шығары: Венесуэла, Мадуро, мұнай саясаты, президент, экономика

Кіріс: Қазақстан айлық есеп, Бір белдік бағыт ынтымақ жобаларына назар аудару
Шығары: Қазақстан, Бір белдік, ынтымақ жобалар, Қытай-Қазақстан қарым-қатынасы, экономикалық сауда

Қосымша: қытай және қазақ тіркестерінің сәйкес сөздерін де қосқылаңыз (мысалы: 中国-Қазақстан, 一带一路, 经济)"""
        else:
            system_prompt = f"""你是一个专业的新闻分析助手，擅长从报告标题和要求中提取核心关键字。

请遵循以下规则：
1. 提取 {max_keywords} 个以内最重要的关键字
2. 关键字应该简明扼要，通常是 2-4 个字的名词或名词短语
3. 优先提取人名、地名、机构名、事件名等专有名词
4. 关键字应该能够概括报告的核心主题
5. 按重要性从高到低排序
6. 只返回关键字列表，用逗号分隔，不要有其他内容

例如：
输入：委内瑞拉最近新闻，关注总统马杜罗的石油政策
输出：委内瑞拉,马杜罗,石油政策,总统,经济

输入：哈萨克斯坦月报，关注一带一路合作项目
输出：哈萨克斯坦,一带一路,合作项目,中哈关系,经济贸易

重要：同时提供中文和哈萨克语的关键字（如果适用），用逗号分隔
例如：哈萨克斯坦, Қазақстан, 一带一路, Бір белдік, 经济, экономика"""

        user_message = f"""报告标题：{title}
时间范围：{time_range_desc}（{time_start.strftime('%Y-%m-%d')} 至 {time_end.strftime('%Y-%m-%d')}）"""

        if user_prompt:
            user_message += f"""
用户要求：{user_prompt}"""

        user_message += f"""

请生成 {max_keywords} 个关键字，用逗号分隔："""

        try:
            logger.info(f"正在使用 AI 生成关键字: {title}")

            response_content = ""
            async for chunk in self.ai_client.chat(
                user_message=user_message,
                system_prompt=system_prompt,
            ):
                response_content += chunk

            # 解析 AI 响应，提取关键字
            keywords = self._parse_keywords(response_content, max_keywords)
            logger.info(f"AI 生成关键字成功: {keywords}")
            return keywords

        except Exception as e:
            logger.error(f"AI 生成关键字失败: {e}", exc_info=True)
            # 失败时使用简单的 fallback 方法
            return self._fallback_keywords(title, user_prompt, max_keywords)

    def _parse_keywords(self, ai_response: str, max_keywords: int) -> list[str]:
        """解析 AI 响应，提取关键字列表（支持中文、英文和哈萨克语）"""
        # 移除多余的空白和换行
        response = ai_response.strip()

        # 按逗号、顿号、空格等分隔符分割
        import re
        # 匹配中文（2-4字）、英文（2-10字符）、哈萨克语/西里尔字母（2-15字符）
        keywords = re.findall(r'[\u4e00-\u9fff]{2,4}|[a-zA-Z]{2,10}|[\u0400-\u04FF]{2,15}', response)

        # 去重并限制数量
        unique_keywords = []
        seen = set()
        for kw in keywords:
            if kw not in seen:
                unique_keywords.append(kw)
                seen.add(kw)
                if len(unique_keywords) >= max_keywords:
                    break

        return unique_keywords

    def _fallback_keywords(self, title: str, user_prompt: str | None, max_keywords: int) -> list[str]:
        """fallback 方法：从标题中提取关键字"""
        import jieba

        # 从标题中提取
        title_words = list(jieba.cut(title))
        stopwords = {'的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '报告', '周报', '月报', '分析', '汇总', '最近', '生成'}

        keywords = []
        for word in title_words:
            word = word.strip()
            if len(word) >= 2 and word not in stopwords:
                keywords.append(word)

        return keywords[:max_keywords]
