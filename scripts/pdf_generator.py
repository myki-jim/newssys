#!/usr/bin/env python3
"""
Clean PDF generation framework for news analysis reports.
Usage: from scripts.pdf_generator import PDFBuilder
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle, PageBreak, Image,
    BaseDocTemplate, PageTemplate, Frame,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import platform

# ── Font registration (cross-platform) ───────────────────────────────────
_FONT_PATHS = {
    "Darwin": {
        "Heiti": "/System/Library/Fonts/STHeiti Medium.ttc",
        "Songti-Bold": "/System/Library/Fonts/Supplemental/Songti.ttc",
    },
    "Linux": {
        "Heiti": "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "Songti-Bold": "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    },
}

_FONT = "Heiti"
_FONT_BOLD = "Songti-Bold"
_REGISTERED = False


def register_fonts():
    """Register Chinese fonts. Safe to call multiple times."""
    global _REGISTERED
    if _REGISTERED:
        return
    system = platform.system()
    paths = _FONT_PATHS.get(system, _FONT_PATHS["Linux"])
    for name, path in paths.items():
        if os.path.exists(path):
            try:
                subfont = 1 if "Medium" in path else 0
                pdfmetrics.registerFont(TTFont(name, path, subfontIndex=subfont))
            except Exception:
                try:
                    pdfmetrics.registerFont(TTFont(name, path))
                except Exception:
                    pass
    _REGISTERED = True


# ── Colors ────────────────────────────────────────────────────────────────
COLOR_DARK = HexColor("#1a365d")
COLOR_BLUE = HexColor("#2b6cb0")
COLOR_TEXT = HexColor("#2d3748")
COLOR_GRAY = HexColor("#718096")
COLOR_BORDER = HexColor("#cbd5e0")
COLOR_HEADER_BG = HexColor("#f7fafc")
COLOR_SUBTITLE = HexColor("#4a5568")
COLOR_ACCENT = HexColor("#3182ce")
COLOR_GREEN = HexColor("#38a169")
COLOR_RED = HexColor("#e53e3e")


# ── Paragraph styles ──────────────────────────────────────────────────────
def _ms(name, **kw):
    """Make a paragraph style with defaults."""
    d = dict(
        fontName=_FONT, fontSize=10.5, leading=15,
        textColor=COLOR_TEXT, alignment=TA_LEFT,
        spaceBefore=2, spaceAfter=2,
    )
    d.update(kw)
    return ParagraphStyle(name, **d)


# Pre-built styles
STYLE_TITLE = _ms("Title", fontName=_FONT_BOLD, fontSize=20, leading=28,
                   textColor=COLOR_DARK, alignment=TA_CENTER, spaceAfter=6)
STYLE_SUBTITLE = _ms("Subtitle", fontSize=12, leading=18,
                      textColor=COLOR_SUBTITLE, alignment=TA_CENTER, spaceAfter=30)
STYLE_H2 = _ms("H2", fontName=_FONT_BOLD, fontSize=14, leading=22,
               textColor=COLOR_DARK, spaceBefore=14, spaceAfter=6)
STYLE_H3 = _ms("H3", fontName=_FONT_BOLD, fontSize=11.5, leading=18,
               textColor=COLOR_BLUE, spaceBefore=10, spaceAfter=5)
STYLE_BODY = _ms("Body")
STYLE_BODY_INDENT = _ms("BodyIndent", firstLineIndent=21)
STYLE_CAPTION = _ms("Caption", fontSize=9, leading=13, textColor=COLOR_GRAY,
                     alignment=TA_CENTER, spaceBefore=4, spaceAfter=16)
STYLE_CELL = _ms("Cell", fontSize=10, leading=14)
STYLE_CELL_BOLD = _ms("CellBold", fontName=_FONT_BOLD, fontSize=10, leading=14)
STYLE_CELL_CENTER = _ms("CellCenter", fontSize=10, leading=14, alignment=TA_CENTER)
STYLE_SIGN = _ms("Sign", fontSize=10.5, leading=20)
STYLE_SIGN_BOLD = _ms("SignBold", fontName=_FONT_BOLD, fontSize=10.5, leading=16)
STYLE_SMALL = _ms("Small", fontSize=9, leading=13, textColor=COLOR_GRAY)
STYLE_BLOCKQUOTE = _ms("Blockquote", fontSize=10, leading=16, textColor=COLOR_SUBTITLE,
                         leftIndent=12, borderPadding=6)


# ── Quick content helpers ─────────────────────────────────────────────────
def h2(text):
    """Section heading."""
    return Paragraph(text, STYLE_H2)


def h3(text):
    """Sub-section heading."""
    return Paragraph(text, STYLE_H3)


def p(text):
    """Body paragraph."""
    return Paragraph(text, STYLE_BODY)


def pi(text):
    """Body paragraph with first-line indent."""
    return Paragraph(text, STYLE_BODY_INDENT)


def small(text):
    """Small gray text."""
    return Paragraph(text, STYLE_SMALL)


def caption(text):
    """Image/table caption."""
    return Paragraph(text, STYLE_CAPTION)


def bold_cell(text):
    """Bold table cell."""
    return Paragraph(text, STYLE_CELL_BOLD)


def cell(text):
    """Normal table cell."""
    return Paragraph(text, STYLE_CELL)


def center_cell(text, bold=False):
    """Centered table cell."""
    s = STYLE_CELL_BOLD if bold else STYLE_CELL_CENTER
    return Paragraph(text, s)


# ── Table helpers ─────────────────────────────────────────────────────────
def styled_table(data, col_widths, header_rows=1):
    """Create a table with standard styling (header bg, grid, padding)."""
    t = Table(data, colWidths=col_widths, repeatRows=header_rows)
    style_cmds = [
        ("FONTNAME", (0, 0), (-1, -1), _FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    if header_rows > 0:
        style_cmds.append(("BACKGROUND", (0, 0), (-1, header_rows - 1), COLOR_HEADER_BG))
    t.setStyle(TableStyle(style_cmds))
    return t


def key_value_table(pairs, key_width_ratio=0.2):
    """Create a key-value table from a list of (label, value) tuples."""
    data = [[bold_cell(k), cell(v)] for k, v in pairs]
    w = A4[0] - 30 * mm
    return styled_table(data, [w * key_width_ratio, w * (1 - key_width_ratio)], header_rows=0)


# ── Footer ────────────────────────────────────────────────────────────────
def _make_footer(label):
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(_FONT, 9)
        canvas.setFillColor(COLOR_GRAY)
        canvas.drawString(15 * mm, 12 * mm, label)
        canvas.drawRightString(A4[0] - 15 * mm, 12 * mm, f"{canvas.getPageNumber()} / {doc.page}")
        canvas.restoreState()
    return footer


# ═══════════════════════════════════════════════════════════════════════════
#  PDF Builder — the clean API
# ═══════════════════════════════════════════════════════════════════════════
class PDFBuilder:
    """
    Fluent API for building PDF reports.

    Usage:
        builder = PDFBuilder("report.pdf", title="My Report", footer_label="My Report")
        builder.add_title("My Report", subtitle="Generated by NewsSys")
        builder.add_h2("Section 1")
        builder.add_p("Paragraph text...")
        builder.add_key_value_table([("Key", "Value"), ...])
        builder.build()
    """

    def __init__(self, output_path, title="Report", footer_label="Report",
                 pagesize=A4, left_margin=15*mm, right_margin=15*mm,
                 top_margin=20*mm, bottom_margin=20*mm):
        register_fonts()
        self.output_path = output_path
        self.title = title
        self.width = pagesize[0] - left_margin - right_margin
        self.height = pagesize[1] - top_margin - bottom_margin

        self.doc = BaseDocTemplate(
            output_path,
            pagesize=pagesize,
            leftMargin=left_margin,
            rightMargin=right_margin,
            topMargin=top_margin,
            bottomMargin=bottom_margin,
            title=title,
        )
        frame = Frame(left_margin, bottom_margin, self.width, self.height, id="main")
        footer_fn = _make_footer(footer_label)
        self.doc.addPageTemplates([
            PageTemplate(id="First", frames=frame, onPage=footer_fn),
            PageTemplate(id="Later", frames=frame, onPage=footer_fn),
        ])
        self.story = []

    # ── Content methods (chainable) ───────────────────────────────────

    def add_title(self, title, subtitle=None):
        """Add document title and optional subtitle."""
        self.story.append(Spacer(1, 40))
        self.story.append(Paragraph(title, STYLE_TITLE))
        if subtitle:
            self.story.append(Paragraph(subtitle, STYLE_SUBTITLE))
        return self

    def add_h2(self, text):
        self.story.append(Paragraph(text, STYLE_H2))
        return self

    def add_h3(self, text):
        self.story.append(Paragraph(text, STYLE_H3))
        return self

    def add_p(self, text):
        self.story.append(Paragraph(text, STYLE_BODY))
        return self

    def add_pi(self, text):
        self.story.append(Paragraph(text, STYLE_BODY_INDENT))
        return self

    def add_small(self, text):
        self.story.append(Paragraph(text, STYLE_SMALL))
        return self

    def add_caption(self, text):
        self.story.append(Paragraph(text, STYLE_CAPTION))
        return self

    def add_spacer(self, mm_height=6):
        self.story.append(Spacer(1, mm_height))
        return self

    def add_page_break(self):
        self.story.append(PageBreak())
        return self

    def add_table(self, data, col_widths, header_rows=1):
        """Add a styled table."""
        self.story.append(styled_table(data, col_widths, header_rows))
        return self

    def add_key_value_table(self, pairs, key_width_ratio=0.2):
        """Add a key-value style table."""
        self.story.append(key_value_table(pairs, key_width_ratio))
        return self

    def add_image(self, path, width=None, caption_text=None):
        """Add an image with optional caption."""
        w = width or self.width * 0.8
        if os.path.exists(path):
            self.story.append(Image(path, width=w, height=w * 9 / 16, kind='proportional'))
            if caption_text:
                self.story.append(Paragraph(caption_text, STYLE_CAPTION))
        return self

    def add_signature_block(self, party_a="委托方 (甲方)", party_b="服务方 (乙方)"):
        """Add a two-party signature block."""
        self.story.append(Spacer(1, 20))
        sign_data = [[
            Paragraph(f"<b>{party_a}：</b><br/><br/>代表签字（盖章）：<br/><br/>"
                      "______________________________<br/><br/>日期：    年    月    日", STYLE_SIGN),
            Paragraph(f"<b>{party_b}：</b><br/><br/>代表签字（盖章）：<br/><br/>"
                      "______________________________<br/><br/>日期：    年    月    日", STYLE_SIGN),
        ]]
        t = Table(sign_data, colWidths=[self.width * 0.5, self.width * 0.5])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), _FONT),
            ("FONTSIZE", (0, 0), (-1, -1), 10.5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -1), 0, HexColor("#ffffff")),
        ]))
        self.story.append(t)
        return self

    def add_element(self, element):
        """Add any reportlab flowable element directly."""
        self.story.append(element)
        return self

    def build(self):
        """Build and save the PDF."""
        self.doc.build(self.story)
        return self.output_path


# ── CLI entry point ───────────────────────────────────────────────────────
if __name__ == "__main__":
    # Quick demo
    builder = PDFBuilder("/tmp/newsys_demo.pdf", title="Demo Report", footer_label="NewsSys")
    builder.add_title("新闻态势分析报告", subtitle="自动生成于 NewsSys 2.0")
    builder.add_h2("一、 概述")
    builder.add_p("本报告由新闻态势分析系统自动生成，涵盖指定时间范围内的关键舆情事件与趋势分析。")
    builder.add_h2("二、 关键指标")
    builder.add_key_value_table([
        ("时间范围", "2026-05-14 至 2026-05-21"),
        ("采集文章数", "1,234"),
        ("生成事件数", "15"),
        ("活跃采集源", "42"),
    ])
    builder.add_h2("三、 结论")
    builder.add_p("系统运行正常，报告生成完毕。")
    builder.add_signature_block("委托方", "服务方")
    path = builder.build()
    print(f"Demo PDF generated: {path}")
