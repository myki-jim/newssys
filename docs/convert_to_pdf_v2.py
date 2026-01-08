#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 Markdown 文档转换为 PDF (使用 markdown2 + reportlab)
"""

import markdown2
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pathlib import Path
import re
import os

# 文件路径
md_file = Path("/Users/jimmyki/Documents/Code/news/docs/用户手册.md")
pdf_file = Path("/Users/jimmyki/Documents/Code/news/docs/用户手册.pdf")

print(f"正在读取 Markdown 文件: {md_file}")

# 读取 Markdown 文件
with open(md_file, 'r', encoding='utf-8') as f:
    md_content = f.read()

# 注册中文字体
try:
    # 尝试注册系统中文字体
    font_path = "/System/Library/Fonts/PingFang.ttc"
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
        chinese_font = 'ChineseFont'
    else:
        chinese_font = 'Helvetica'
except:
    chinese_font = 'Helvetica'

print(f"正在创建 PDF...")

# 创建 PDF 文档
doc = SimpleDocTemplate(
    str(pdf_file),
    pagesize=A4,
    rightMargin=2*cm,
    leftMargin=2*cm,
    topMargin=2*cm,
    bottomMargin=2*cm
)

# 创建样式
styles = getSampleStyleSheet()

# 添加自定义样式
styles.add(ParagraphStyle(
    name='CustomTitle',
    parent=styles['Heading1'],
    fontName=chinese_font,
    fontSize=24,
    textColor=colors.HexColor('#2c3e50'),
    spaceAfter=20,
    spaceBefore=30,
    leading=28
))

styles.add(ParagraphStyle(
    name='CustomHeading2',
    parent=styles['Heading2'],
    fontName=chinese_font,
    fontSize=18,
    textColor=colors.HexColor('#34495e'),
    spaceAfter=15,
    spaceBefore=20,
    leading=22
))

styles.add(ParagraphStyle(
    name='CustomHeading3',
    parent=styles['Heading3'],
    fontName=chinese_font,
    fontSize=14,
    textColor=colors.HexColor('#7f8c8d'),
    spaceAfter=10,
    spaceBefore=15,
    leading=18
))

styles.add(ParagraphStyle(
    name='CustomNormal',
    parent=styles['Normal'],
    fontName=chinese_font,
    fontSize=10,
    leading=14,
    alignment=TA_JUSTIFY,
    spaceAfter=10
))

styles.add(ParagraphStyle(
    name='CustomCode',
    parent=styles['Code'],
    fontName='Courier',
    fontSize=9,
    leading=12,
    backColor=colors.HexColor('#f4f4f4'),
    borderColor=colors.HexColor('#ddd'),
    borderWidth=1,
    borderPadding=5,
    spaceAfter=10
))

# 解析 Markdown 并构建文档元素
story = []
lines = md_content.split('\n')
in_code_block = False
code_lines = []

for line in lines:
    # 处理代码块
    if line.startswith('```'):
        if in_code_block:
            # 结束代码块
            code_text = '\n'.join(code_lines)
            story.append(Paragraph(code_text.replace('<', '&lt;').replace('>', '&gt;'), styles['CustomCode']))
            code_lines = []
            in_code_block = False
        else:
            in_code_block = True
        continue

    if in_code_block:
        code_lines.append(line)
        continue

    # 处理图片
    if line.startswith('!['):
        story.append(Spacer(1, 0.5*cm))
        continue

    # 处理标题
    if line.startswith('# '):
        text = line[2:].strip()
        story.append(Paragraph(text, styles['CustomTitle']))
        story.append(Spacer(1, 0.3*cm))
    elif line.startswith('## '):
        text = line[3:].strip()
        story.append(Paragraph(text, styles['CustomHeading2']))
        story.append(Spacer(1, 0.2*cm))
    elif line.startswith('### '):
        text = line[4:].strip()
        story.append(Paragraph(text, styles['CustomHeading3']))
        story.append(Spacer(1, 0.2*cm))
    elif line.startswith('#### '):
        text = line[5:].strip()
        story.append(Paragraph(text, styles['CustomHeading3']))
        story.append(Spacer(1, 0.2*cm))

    # 处理分隔线
    elif line.strip() == '---':
        story.append(Spacer(1, 0.5*cm))

    # 处理表格
    elif '|' in line and line.strip().startswith('|'):
        # 简单的表格处理 - 跳过
        continue

    # 处理列表
    elif line.strip().startswith('- ') or line.strip().startswith('* '):
        text = line.strip()[2:]
        story.append(Paragraph(f"• {text}", styles['CustomNormal']))

    # 处理编号列表
    elif re.match(r'^\d+\.\s', line.strip()):
        text = re.sub(r'^\d+\.\s', '', line.strip())
        story.append(Paragraph(text, styles['CustomNormal']))

    # 处理普通段落
    elif line.strip() and not line.startswith('#'):
        # 移除 Markdown 格式
        text = line.strip()
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # 粗体
        text = re.sub(r'\*(.*?)\*', r'\1', text)  # 斜体
        text = re.sub(r'`(.*?)`', r'\1', text)  # 代码
        text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)  # 链接

        if text:
            story.append(Paragraph(text, styles['CustomNormal']))

    # 处理空行
    elif not line.strip():
        story.append(Spacer(1, 0.3*cm))

# 构建 PDF
print(f"正在生成 PDF: {pdf_file}")
doc.build(story)

print(f"\n✓ 转换完成！")
print(f"  - PDF: {pdf_file}")
print(f"  - 文件大小: {pdf_file.stat().st_size / 1024:.1f} KB")
