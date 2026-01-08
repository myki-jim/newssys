"""
报告模板管理器
管理预设的报告模板和配置
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReportTemplate:
    """
    报告模板
    """

    id: str  # 模板 ID
    name: str  # 模板名称
    description: str  # 模板描述

    # AI 提示词
    system_prompt: str  # 系统提示词
    user_prompt_template: str  # 用户提示词模板

    # 筛选配置
    keywords: list[str] = field(default_factory=list)  # 关键词筛选
    source_ids: list[int] = field(default_factory=list)  # 指定的源 ID
    time_range: str = 'week'  # 时间范围 ('week', 'month')

    # 报告配置
    include_references: bool = True  # 是否包含参考文献
    include_statistics: bool = True  # 是否包含统计信息
    max_articles: int = 20  # 最大文章数

    # 输出格式
    output_format: str = 'markdown'  # 'markdown', 'html', 'json'

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'system_prompt': self.system_prompt,
            'user_prompt_template': self.user_prompt_template,
            'keywords': self.keywords,
            'source_ids': self.source_ids,
            'time_range': self.time_range,
            'include_references': self.include_references,
            'include_statistics': self.include_statistics,
            'max_articles': self.max_articles,
            'output_format': self.output_format,
        }


# 预设模板库
PRESET_TEMPLATES: dict[str, ReportTemplate] = {
    'kazakhstan_politics_weekly': ReportTemplate(
        id='kazakhstan_politics_weekly',
        name='哈萨克斯坦政治周报',
        description='每周哈萨克斯坦政治动态汇总分析',
        system_prompt="""你是一位专业的中亚政治分析专家。你的任务是基于提供的新闻文章，生成一份高质量的哈萨克斯坦政治周报。

报告要求：
1. 内容结构清晰，包含以下部分：
   - 本周要闻摘要
   - 政治动态分析
   - 政策变化解读
   - 下周展望

2. 分析深度：
   - 不仅仅陈述事实，更要分析背后的政治含义
   - 识别关键趋势和潜在影响
   - 连接不同事件之间的关联

3. 引用规范：
   - 每个重要观点后必须添加引用标记 [1], [2] 等
   - 引用必须与提供的文章严格对应
   - 不得编造或虚构任何信息

4. 语言风格：
   - 专业、客观、准确
   - 使用清晰的政治术语
   - 避免主观臆断""",
        user_prompt_template="""请基于以下新闻文章，生成一份哈萨克斯坦政治周报：

{context}

请按照要求的格式生成报告，确保每个重要观点都有正确的引用。""",
        keywords=['哈萨克斯坦', '政治', '总统', '政府', '政策', '选举'],
        time_range='week',
        max_articles=15,
    ),

    'central_asia_security': ReportTemplate(
        id='central_asia_security',
        name='中亚安全态势分析',
        description='中亚地区安全形势和军事动态分析',
        system_prompt="""你是一位资深的地区安全事务分析师。你的任务是分析中亚地区的安全态势。

报告要求：
1. 内容结构：
   - 安全形势概述
   - 各国军事动态
   - 反恐与边境安全
   - 大国博弈与地区合作
   - 风险评估与预警

2. 分析重点：
   - 识别潜在的冲突热点
   - 分析军事演习和部署的意图
   - 评估恐怖主义威胁
   - 解读大国在中亚的军事存在

3. 引用规范：
   - 所有事实陈述必须有引用
   - 分析结论需基于提供的材料

4. 语言风格：
   - 专业、严谨
   - 适当使用军事和安全术语""",
        user_prompt_template="""请基于以下材料，分析中亚地区的安全态势：

{context}

生成专业的安全态势分析报告。""",
        keywords=['安全', '军事', '反恐', '边境', '演习', '国防'],
        time_range='week',
        max_articles=20,
    ),

    'energy_industry': ReportTemplate(
        id='energy_industry',
        name='中亚能源行业动态',
        description='中亚地区能源、石油天然气行业分析',
        system_prompt="""你是一位能源行业分析专家。请基于提供的新闻，分析中亚地区的能源行业动态。

报告要求：
1. 内容结构：
   - 行业概览
   - 主要项目进展
   - 政策与法规变化
   - 国际合作动态
   - 市场趋势分析

2. 分析重点：
   - 油气项目进展和投资
   - 能源政策变化
   - 区域能源合作
   - 新能源发展

3. 数据支撑：
   - 使用具体数据支撑分析
   - 所有引用必须准确""",
        user_prompt_template="""请分析中亚能源行业的最新动态：

{context}

生成专业的能源行业分析报告。""",
        keywords=['能源', '石油', '天然气', '电力', '新能源', '项目'],
        time_range='week',
        max_articles=15,
    ),

    'general_news_summary': ReportTemplate(
        id='general_news_summary',
        name='通用新闻摘要',
        description='通用新闻汇总，适用于各种主题',
        system_prompt="""你是一位专业的新闻编辑。请基于提供的文章，生成一份结构清晰、重点突出的新闻摘要报告。

报告要求：
1. 结构：
   - 头条要闻
   - 分类新闻（政治、经济、社会等）
   - 快讯简报

2. 内容：
   - 简洁明了
   - 重点突出
   - 准确客观

3. 引用：
   - 所有事实陈述必须有引用""",
        user_prompt_template="""请生成一份新闻摘要报告：

{context}

按照标准格式组织报告。""",
        keywords=[],
        time_range='week',
        max_articles=20,
    ),

    'competitive_analysis': ReportTemplate(
        id='competitive_analysis',
        name='竞品分析报告',
        description='行业竞品动态和市场分析',
        system_prompt="""你是一位市场分析专家。请基于提供的新闻，生成竞品分析报告。

报告要求：
1. 结构：
   - 市场概况
   - 主要竞品动态
   - 产品/服务对比
   - 市场趋势预测

2. 分析：
   - 客观中立
   - 数据驱动
   - 注重实用性

3. 引用规范严格""",
        user_prompt_template="""请基于以下信息，生成竞品分析报告：

{context}

生成专业的竞品分析。""",
        keywords=['竞品', '市场', '发布', '更新', '产品', '服务'],
        time_range='month',
        max_articles=25,
    ),
}


class TemplateManager:
    """
    模板管理器
    """

    def __init__(self) -> None:
        """初始化模板管理器"""
        self.templates = PRESET_TEMPLATES.copy()

    def get_template(self, template_id: str) -> ReportTemplate | None:
        """
        获取模板

        Args:
            template_id: 模板 ID

        Returns:
            模板对象，不存在返回 None
        """
        return self.templates.get(template_id)

    def list_templates(self) -> list[dict[str, Any]]:
        """
        列出所有模板

        Returns:
            模板信息列表
        """
        return [
            {
                'id': t.id,
                'name': t.name,
                'description': t.description,
            }
            for t in self.templates.values()
        ]

    def add_template(self, template: ReportTemplate) -> None:
        """
        添加自定义模板

        Args:
            template: 模板对象
        """
        self.templates[template.id] = template

    def remove_template(self, template_id: str) -> bool:
        """
        删除模板

        Args:
            template_id: 模板 ID

        Returns:
            是否成功删除
        """
        if template_id in self.templates:
            del self.templates[template_id]
            return True
        return False

    def create_custom_template(
        self,
        template_id: str,
        name: str,
        description: str,
        system_prompt: str,
        user_prompt_template: str,
        **kwargs: Any,
    ) -> ReportTemplate:
        """
        创建自定义模板

        Args:
            template_id: 模板 ID
            name: 模板名称
            description: 模板描述
            system_prompt: 系统提示词
            user_prompt_template: 用户提示词模板
            **kwargs: 其他配置参数

        Returns:
            新创建的模板
        """
        template = ReportTemplate(
            id=template_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            **kwargs,
        )

        self.add_template(template)
        return template

    def build_prompt(
        self,
        template_id: str,
        context: str,
        user_requirements: str | None = None,
    ) -> tuple[str, str]:
        """
        根据模板构建完整的提示词

        Args:
            template_id: 模板 ID
            context: 上下文内容
            user_requirements: 用户额外要求（可选）

        Returns:
            (system_prompt, user_prompt) 元组
        """
        template = self.get_template(template_id)
        if template is None:
            raise ValueError(f"Template not found: {template_id}")

        system_prompt = template.system_prompt

        user_prompt = template.user_prompt_template.format(context=context)

        if user_requirements:
            user_prompt = f"\n\n用户额外要求：\n{user_requirements}\n\n{user_prompt}"

        return system_prompt, user_prompt

    def get_template_config(self, template_id: str) -> dict[str, Any] | None:
        """
        获取模板的筛选配置

        Args:
            template_id: 模板 ID

        Returns:
            配置字典
        """
        template = self.get_template(template_id)
        if template is None:
            return None

        return {
            'keywords': template.keywords,
            'source_ids': template.source_ids,
            'time_range': template.time_range,
            'max_articles': template.max_articles,
        }


# 全局模板管理器实例
template_manager = TemplateManager()


# 便捷函数
def get_preset_templates() -> list[str]:
    """获取所有预设模板 ID"""
    return list(PRESET_TEMPLATES.keys())


def get_template(template_id: str) -> ReportTemplate | None:
    """获取模板"""
    return template_manager.get_template(template_id)
