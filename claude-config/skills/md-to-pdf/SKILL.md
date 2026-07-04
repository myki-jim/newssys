---
name: md-to-pdf
description: >
  Convert markdown content to PDF and publish to render-server.
  Use whenever you need to generate a PDF report from markdown text.
  Eliminates the need to write custom Python PDF generation code.
  Triggered by: generate PDF, create report, publish report, export PDF.
version: 1.0.0
allowed-tools: [Bash]
user-invocable: true
---

# MD-to-PDF Converter

将 markdown 内容转换为 PDF 并发布到 render-server。**不要再手写 Python PDF 代码！** 用这个 skill。

## 使用方法

### 基本用法 (推荐)

将 markdown 内容写入文件，然后运行：

```bash
python3 /root/.claude/skills/md-to-pdf/generate_pdf.py --file /workspace/report.md
```

### 通过管道传入

```bash
cat report.md | python3 /root/.claude/skills/md-to-pdf/generate_pdf.py
```

### 带元数据 (YAML frontmatter)

在 markdown 文件开头添加元数据：

```markdown
---
title: 2026年5月22日 全球要闻日报
subtitle: 基于内部爬虫数据编撰
footer: 全球要闻日报
---
# 一、今日概览
...
```

### 使用模板

```bash
python3 /root/.claude/skills/md-to-pdf/generate_pdf.py \
  --template /root/.claude/skills/md-to-pdf/templates/default.md \
  --vars '{"title":"日报标题","date":"2026-05-22"}' \
  < content.md
```

### 跳过上传 (仅生成PDF)

```bash
python3 /root/.claude/skills/md-to-pdf/generate_pdf.py --no-upload --file report.md
```

## 支持的 Markdown 语法

- `# 标题` — 报告标题
- `## 章节` — 一级章节 (H2)
- `### 小节` — 二级章节 (H3)
- `- 列表项` — 项目符号
- `| 表格 | 数据 |` — 表格 (首行为表头)
- `---` — 分页符
- `> 引用` — 引用块
- `**粗体**` `*斜体*` — 文字样式

## 返回值

成功时输出 JSON：
```json
{"url": "http://192.168.100.108:8081/view/abc123", "id": "abc123"}
```

## 模板

内置模板位于 `/root/.claude/skills/md-to-pdf/templates/`:
- `default.md` — 详细报告模板 (默认)
- `brief.md` — 简报模板

用户可以在 workspace 文件夹中创建自定义模板文件。
