#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 Markdown 文档转换为 PDF
"""

import markdown
from weasyprint import HTML, CSS
from pathlib import Path

# 文件路径
md_file = Path("/Users/jimmyki/Documents/Code/news/docs/用户手册.md")
html_file = Path("/Users/jimmyki/Documents/Code/news/docs/用户手册.html")
pdf_file = Path("/Users/jimmyki/Documents/Code/news/docs/用户手册.pdf")

print(f"正在读取 Markdown 文件: {md_file}")

# 读取 Markdown 文件
with open(md_file, 'r', encoding='utf-8') as f:
    md_content = f.read()

print(f"正在转换为 HTML...")

# 转换 Markdown 为 HTML
html_content = markdown.markdown(
    md_content,
    extensions=['tables', 'fenced_code', 'nl2br', 'sane_lists']
)

# 添加样式和图片路径
full_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>新闻态势分析系统 - 用户手册</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm;
            @bottom-center {{
                content: "第 " counter(page) " 页";
                font-size: 10pt;
                color: #666;
            }}
        }}

        body {{
            font-family: "Microsoft YaHei", "SimHei", "PingFang SC", -apple-system, BlinkMacSystemFont, sans-serif;
            line-height: 1.8;
            padding: 0;
            margin: 0;
            color: #333;
            font-size: 11pt;
        }}

        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-top: 30px;
            margin-bottom: 20px;
            font-size: 24pt;
            page-break-after: avoid;
        }}

        h2 {{
            color: #34495e;
            border-bottom: 2px solid #95a5a6;
            padding-bottom: 8px;
            margin-top: 25px;
            margin-bottom: 15px;
            font-size: 18pt;
            page-break-after: avoid;
        }}

        h3 {{
            color: #7f8c8d;
            margin-top: 20px;
            margin-bottom: 10px;
            font-size: 14pt;
            page-break-after: avoid;
        }}

        h4 {{
            color: #95a5a6;
            margin-top: 15px;
            margin-bottom: 8px;
            font-size: 12pt;
            page-break-after: avoid;
        }}

        p {{
            margin-bottom: 10px;
            text-align: justify;
        }}

        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
            font-size: 10pt;
            page-break-inside: avoid;
        }}

        th {{
            background-color: #3498db;
            color: white;
            padding: 8px;
            text-align: left;
            font-weight: bold;
            border: 1px solid #2980b9;
        }}

        td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}

        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}

        img {{
            max-width: 100%;
            height: auto;
            margin: 20px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
            page-break-inside: avoid;
        }}

        code {{
            background-color: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: "Consolas", "Monaco", monospace;
            font-size: 9pt;
            color: #c7254e;
        }}

        pre {{
            background-color: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            page-break-inside: avoid;
            border: 1px solid #ddd;
        }}

        pre code {{
            background-color: transparent;
            padding: 0;
            color: #333;
        }}

        ul, ol {{
            margin-left: 20px;
            margin-bottom: 10px;
        }}

        li {{
            margin-bottom: 5px;
        }}

        a {{
            color: #3498db;
            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
        }}

        blockquote {{
            border-left: 4px solid #3498db;
            padding-left: 15px;
            margin: 15px 0;
            color: #666;
            font-style: italic;
        }}

        hr {{
            border: none;
            border-top: 2px solid #eee;
            margin: 30px 0;
        }}

        .page-break {{
            page-break-after: always;
        }}
    </style>
</head>
<body>
{html_content}
</body>
</html>
"""

print(f"正在保存 HTML 文件: {html_file}")

# 保存 HTML
with open(html_file, 'w', encoding='utf-8') as f:
    f.write(full_html)

print(f"正在转换为 PDF: {pdf_file}")

# 转换为 PDF
HTML(string=full_html, base_url=str(md_file.parent)).write_pdf(str(pdf_file))

print(f"\n✓ 转换完成！")
print(f"  - HTML: {html_file}")
print(f"  - PDF: {pdf_file}")
print(f"  - 文件大小: {pdf_file.stat().st_size / 1024:.1f} KB")
