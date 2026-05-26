---
name: pdf-report
description: >
  Use whenever the user asks to generate a PDF report, export to PDF, create a document,
  produce a formatted report, make a user manual, or output a professional document.
  General-purpose PDF generation with Chinese font support, tables, images, and
  professional styling. Works for news reports, OSINT dossiers, investigation reports,
  knowledge graphs, system manuals, or any structured document.
  Triggered by keywords: PDF, generate report, export, document, user manual, 生成PDF, 导出, 报告, 文档.
version: 1.0.0
allowed-tools: [Bash, Write, Read]
user-invocable: true
---

# PDF Report Generator (通用)

Framework at `/workspace/scripts/pdf_generator.py` — provides `PDFBuilder` class. Reportlab-based with Chinese fonts (Heiti/Songti).

## Quick start

```python
import sys; sys.path.insert(0, '/workspace')
from scripts.pdf_generator import PDFBuilder, h2, h3, p, pi, cell, bold_cell, styled_table

builder = PDFBuilder("/workspace/output.pdf", title="Report Title", footer_label="Footer Label")
builder.add_title("报告标题", subtitle="副标题 (可选)")
builder.add_h2("一、 章节标题")
builder.add_p("正文段落内容...")
builder.add_key_value_table([("键", "值")])
builder.build()
print("PDF generated:", builder.output_path)
```

## API reference

### Constructor
`PDFBuilder(output_path, title="Report", footer_label="Report")`

### Content methods (chainable, return self)

| Method | Description |
|--------|-------------|
| `add_title(title, subtitle=None)` | Document title + optional subtitle centered |
| `add_h2(text)` | Section heading (bold, dark blue, 14pt) |
| `add_h3(text)` | Sub-section heading (bold, medium blue, 11.5pt) |
| `add_p(text)` | Body paragraph (10.5pt) |
| `add_pi(text)` | Body paragraph with first-line indent |
| `add_small(text)` | Small gray text (9pt) |
| `add_caption(text)` | Centered caption for images/tables |
| `add_spacer(mm=6)` | Vertical whitespace |
| `add_page_break()` | Force new page |
| `add_table(data, col_widths, header_rows=1)` | Styled table (header bg, grid, padding) |
| `add_key_value_table(pairs, key_width_ratio=0.2)` | Key-value metadata table |
| `add_image(path, width=None, caption_text=None)` | Image with proportional scaling |
| `add_signature_block(party_a, party_b)` | Two-party signature area |
| `add_element(element)` | Any reportlab flowable directly |

### Helpers (import from pdf_generator)
`h2(text)` `h3(text)` `p(text)` `pi(text)` `small(text)` `caption(text)` `cell(text)` `bold_cell(text)` `center_cell(text, bold=False)` `styled_table(data, col_widths, header_rows=1)` `key_value_table(pairs, key_width_ratio=0.2)`

### Colors
`COLOR_DARK` `COLOR_BLUE` `COLOR_TEXT` `COLOR_GRAY` `COLOR_BORDER` `COLOR_HEADER_BG` `COLOR_ACCENT` `COLOR_GREEN` `COLOR_RED`

## Report type examples

### OSINT person dossier
```python
builder.add_title("人员调查档案", subtitle="基于公开信息生成")
builder.add_h2("一、 身份概要")
builder.add_key_value_table([("姓名", name), ("已知邮箱", email), ("关联账号", accounts)])
builder.add_h2("二、 社交媒体活动")
builder.add_p("各平台公开信息汇总...")
builder.add_h2("三、 关联人物与组织")
builder.add_h2("四、 风险指标")
builder.add_h2("五、 信息来源")
```

### Investigation / news report
```python
builder.add_title("舆情分析报告", subtitle=f"时间范围: {start} 至 {end}")
builder.add_h2("一、 概述")
builder.add_h2("二、 关键发现")
builder.add_h2("三、 事件时间线")
builder.add_h2("四、 趋势分析")
builder.add_h2("五、 结论与建议")
builder.add_h2("六、 参考来源")
```

### Knowledge graph report
```python
builder.add_title("知识图谱分析", subtitle=entity_name)
builder.add_h2("一、 实体清单")
builder.add_h2("二、 关系矩阵")
builder.add_h2("三、 网络图谱")  # Mermaid rendered as text
builder.add_h2("四、 关键节点分析")
```

### System health / manual
```python
builder.add_title("系统健康报告", subtitle=hostname)
builder.add_key_value_table([("CPU", cpu), ("内存", mem), ("磁盘", disk)])
builder.add_h2("一、 各服务状态")
builder.add_h2("二、 告警与建议")
```

## Publishing via Render Server

After generating the PDF, publish it to the render server so the user gets a browser-viewable URL:

```bash
# Publish the generated PDF (base64-encoded)
PDF_BASE64=$(base64 -i /workspace/output.pdf | tr -d '\n')
curl -s -X POST "http://render-server:8000/api/publish" \
  --form-string "title=Report Title" \
  --form-string "content=$PDF_BASE64" \
  --form-string "content_type=pdf_base64"
# Returns: {"url": "/view/abc123", "id": "abc123"}
```

Report the returned URL to the user: `http://192.168.20.26:8081/view/{id}`

## Style conventions
- Sections: `一、二、三...` with `add_h2()`, sub-sections: `1. 2. 3...` with `add_h3()`
- Long prose: `add_pi()` (indented), short descriptions: `add_p()`
- Metadata: `add_key_value_table()`, data tables: `add_table()`
- Always end with source references
- Footer shows page number: `page N / total`
