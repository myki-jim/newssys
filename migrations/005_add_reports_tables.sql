-- 报告生成相关表

-- 报告模板表
CREATE TABLE IF NOT EXISTS report_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    system_prompt TEXT NOT NULL,
    section_template TEXT DEFAULT '[]', -- JSON格式的板块模板
    is_default INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 报告表
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    time_range_start TIMESTAMP NOT NULL,
    time_range_end TIMESTAMP NOT NULL,
    template_id INTEGER,
    custom_prompt TEXT,
    language TEXT DEFAULT 'zh', -- zh=中文, kk=哈萨克语
    max_events INTEGER DEFAULT 10, -- 最大事件数量

    -- 统计信息
    total_articles INTEGER DEFAULT 0,
    clustered_articles INTEGER DEFAULT 0,
    event_count INTEGER DEFAULT 0,

    -- 报告内容
    content TEXT, -- Markdown格式的完整报告
    sections TEXT DEFAULT '[]', -- JSON格式的板块列表

    -- 状态
    status TEXT DEFAULT 'draft', -- draft, generating, completed, failed
    agent_stage TEXT DEFAULT 'initializing', -- Agent阶段
    agent_progress INTEGER DEFAULT 0,
    agent_message TEXT DEFAULT '',

    error_message TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    FOREIGN KEY (template_id) REFERENCES report_templates(id) ON DELETE SET NULL
);

-- 报告事件表（重点事件）
CREATE TABLE IF NOT EXISTS report_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    event_title TEXT NOT NULL,
    event_summary TEXT,
    article_count INTEGER DEFAULT 0,
    keywords TEXT DEFAULT '[]', -- JSON格式的事件关键词
    importance_score REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
);

-- 报告板块表
CREATE TABLE IF NOT EXISTS report_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    section_title TEXT NOT NULL,
    section_content TEXT,
    section_order INTEGER DEFAULT 0,
    event_ids TEXT DEFAULT '[]', -- JSON格式的事件ID列表
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE
);

-- 报告文章关联表
CREATE TABLE IF NOT EXISTS report_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    article_id INTEGER NOT NULL,
    event_id INTEGER,
    is_representative INTEGER DEFAULT 0, -- 是否为代表文章
    citation_index INTEGER, -- 引用序号
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
    FOREIGN KEY (event_id) REFERENCES report_events(id) ON DELETE SET NULL
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_time_range ON reports(time_range_start, time_range_end);

CREATE INDEX IF NOT EXISTS idx_report_events_report_id ON report_events(report_id);
CREATE INDEX IF NOT EXISTS idx_report_events_importance ON report_events(importance_score DESC);

CREATE INDEX IF NOT EXISTS idx_report_sections_report_id ON report_sections(report_id);
CREATE INDEX IF NOT EXISTS idx_report_sections_order ON report_sections(section_order);

CREATE INDEX IF NOT EXISTS idx_report_articles_report_id ON report_articles(report_id);
CREATE INDEX IF NOT EXISTS idx_report_articles_article_id ON report_articles(article_id);
CREATE INDEX IF NOT EXISTS idx_report_articles_event_id ON report_articles(event_id);

-- 插入默认报告模板
INSERT OR IGNORE INTO report_templates (id, name, description, system_prompt, section_template, is_default) VALUES
(1, '默认新闻周报', '默认的新闻周报模板', '你是一个专业的新闻分析助手，负责根据给定的新闻事件生成结构化的新闻周报。

请遵循以下规则：
1. 基于事件给出准确、全面的分析
2. 使用专业、客观的语言
3. 报告应结构化、易读
4. 每个板块包含事件概述、详细分析、影响评估
5. 使用Markdown格式', '[
    {"title": "政治要闻", "description": "重要的政治动态和政策变化"},
    {"title": "经济动态", "description": "经济数据、政策调整和市场变化"},
    {"title": "社会热点", "description": "社会关注的热点事件"},
    {"title": "国际关系", "description": "外交活动和国际合作"}
]', 1);

INSERT OR IGNORE INTO report_templates (id, name, description, system_prompt, section_template, is_default) VALUES
(2, '默认新闻月报', '默认的新闻月报模板', '你是一个专业的新闻分析助手，负责根据给定的新闻事件生成结构化的新闻月报。

请遵循以下规则：
1. 对月内重大事件进行深度分析
2. 识别趋势和模式
3. 提供前瞻性见解
4. 使用专业、客观的语言
5. 报告应结构化、易读
6. 使用Markdown格式', '[
    {"title": "月度概览", "description": "本月重要事件总览"},
    {"title": "深度分析", "description": "重点事件的深度分析"},
    {"title": "趋势观察", "description": "识别的趋势和模式"},
    {"title": "下月展望", "description": "基于当前态势的预测"}
]', 0);
