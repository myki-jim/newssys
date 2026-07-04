#!/usr/bin/env python3
"""
MD-to-PDF converter — reliably converts markdown to PDF and uploads to render-server.

Usage:
    echo "# Title\n\nContent" | python3 generate_pdf.py
    python3 generate_pdf.py --file report.md
    python3 generate_pdf.py --template default.md --vars '{"title":"X","date":"Y"}' < content.md

The markdown can have optional YAML frontmatter:
    ---
    title: 报告标题
    subtitle: 副标题
    footer: 页脚标签
    ---
    # Section
    Content...
"""
import sys
import os
import json
import base64
import argparse
import re
import urllib.request
from io import StringIO

# Add workspace scripts to path
sys.path.insert(0, "/workspace")
from scripts.pdf_generator import (
    PDFBuilder, h2, h3, p, pi, cell, bold_cell, center_cell,
    styled_table, key_value_table, COLOR_RED, COLOR_GREEN, COLOR_BLUE,
)


RENDER_SERVER = os.environ.get("RENDER_SERVER_URL", "http://render-server:8000")


def parse_frontmatter(text):
    """Extract YAML-like frontmatter from markdown. Returns (meta, body)."""
    meta = {"title": "Report", "subtitle": "", "footer": "Report"}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                line = line.strip()
                if ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key in meta:
                        meta[key] = val
            body = parts[2].strip()
    return meta, body


def simple_md_to_story(builder, md_text):
    """Convert markdown text to PDFBuilder story elements.

    Supports: # H1, ## H2, ### H3, paragraphs, | tables |, --- pagebreak,
    - bullet lists, > blockquotes, **bold**, *italic*, [links](url)
    """
    lines = md_text.split("\n")
    i = 0
    in_table = False
    table_rows = []
    table_cols = []

    while i < len(lines):
        line = lines[i]

        # Empty line
        if not line.strip():
            if in_table:
                _flush_table(builder, table_rows, table_cols)
                in_table = False
                table_rows = []
                table_cols = []
            i += 1
            continue

        # Page break
        if line.strip() == "---" and not in_table:
            builder.add_page_break()
            i += 1
            continue

        # Table: | col1 | col2 |
        if line.strip().startswith("|") and line.strip().endswith("|"):
            cells = [c.strip() for c in line.strip()[1:-1].split("|")]
            if all(c.startswith("---") or c.startswith(":--") for c in cells if c.strip()):
                # Separator row, skip
                i += 1
                continue
            if not in_table:
                in_table = True
                table_cols = cells
            table_rows.append(cells)
            i += 1
            continue

        # Flush table if we were in one
        if in_table:
            _flush_table(builder, table_rows, table_cols)
            in_table = False
            table_rows = []
            table_cols = []

        # H1
        if line.startswith("# ") and not line.startswith("## "):
            builder.add_title(line[2:].strip())
            i += 1
            continue

        # H2
        if line.startswith("## "):
            builder.add_h2(line[3:].strip())
            i += 1
            continue

        # H3
        if line.startswith("### "):
            builder.add_h3(line[4:].strip())
            i += 1
            continue

        # Bullet list — gather consecutive items
        if line.strip().startswith("- ") or line.strip().startswith("* "):
            items = []
            while i < len(lines) and (lines[i].strip().startswith("- ") or lines[i].strip().startswith("* ")):
                item_text = lines[i].strip()[2:]
                items.append(item_text)
                i += 1
            for item in items:
                bullet = f"• {item}"
                builder.add_p(bullet)
            continue

        # Blockquote
        if line.strip().startswith("> "):
            quotes = []
            while i < len(lines) and lines[i].strip().startswith("> "):
                quotes.append(lines[i].strip()[2:])
                i += 1
            qtext = " ".join(quotes)
            builder.add_p(qtext)
            continue

        # Regular paragraph
        para_lines = []
        while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith("#") and not lines[i].strip().startswith("|") and not lines[i].strip().startswith("- ") and not lines[i].strip().startswith("> ") and not lines[i].strip().startswith("---"):
            para_lines.append(lines[i].strip())
            i += 1
        if para_lines:
            # Handle **bold** and *italic* in paragraphs
            text = " ".join(para_lines)
            builder.add_p(text)

    # Flush any remaining table
    if in_table:
        _flush_table(builder, table_rows, table_cols)


def _flush_table(builder, rows, cols):
    """Add a table to the builder from parsed rows."""
    if not rows:
        return
    ncols = max(len(r) for r in rows)
    # Normalize row lengths
    for r in rows:
        while len(r) < ncols:
            r.append("")
    # Build styled table data with bold headers
    data = []
    for idx, row in enumerate(rows):
        if idx == 0:
            data.append([bold_cell(c) for c in row])
        else:
            data.append([cell(c) for c in row])
    w = builder.width
    cw = w / ncols
    builder.add_table(data, [cw] * ncols, header_rows=1)


def upload_to_render(content_base64, title, content_type="pdf_base64"):
    """Upload a base64-encoded PDF to the render server. Returns the view URL."""
    import urllib.parse
    data = urllib.parse.urlencode({
        "title": title,
        "content": content_base64,
        "content_type": content_type,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{RENDER_SERVER}/api/publish",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return result
    except Exception as e:
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="MD to PDF converter")
    parser.add_argument("--file", help="Input markdown file (default: stdin)")
    parser.add_argument("--template", help="Template file with {variables}")
    parser.add_argument("--vars", help="JSON variables for template substitution")
    parser.add_argument("--output", help="Output PDF path (default: auto-generated in /tmp)")
    parser.add_argument("--no-upload", action="store_true", help="Skip render-server upload")
    args = parser.parse_args()

    # Read input
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            md_text = f.read()
    else:
        md_text = sys.stdin.read()

    # Apply template if provided
    if args.template:
        with open(args.template, "r", encoding="utf-8") as f:
            template = f.read()
        vars_dict = {}
        if args.vars:
            vars_dict = json.loads(args.vars)
        for key, val in vars_dict.items():
            template = template.replace("{" + key + "}", str(val))
        # Append user content after template
        md_text = template + "\n\n" + md_text

    # Extract frontmatter
    meta, body = parse_frontmatter(md_text)

    # Build PDF
    import tempfile
    if args.output:
        output_path = args.output
    else:
        fd, output_path = tempfile.mkstemp(suffix=".pdf", prefix="md2pdf_")
        os.close(fd)

    builder = PDFBuilder(
        output_path,
        title=meta.get("title", "Report"),
        footer_label=meta.get("footer", meta.get("title", "Report")),
    )

    # If title is in frontmatter and body doesn't start with #, add title
    if meta.get("title") and meta.get("subtitle"):
        builder.add_title(meta["title"], subtitle=meta["subtitle"])
    elif meta.get("title"):
        builder.add_title(meta["title"])

    simple_md_to_story(builder, body)
    builder.build()

    print(f"PDF generated: {output_path}", file=sys.stderr)

    # Upload
    if not args.no_upload:
        with open(output_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        result = upload_to_render(b64, meta.get("title", "Report"))
        if "error" in result:
            print(json.dumps(result), file=sys.stderr)
            sys.exit(1)
        view_url = result.get("url", "")
        # Build external URL
        external_host = os.environ.get("EXTERNAL_HOST", "192.168.100.108:8081")
        if view_url.startswith("/view/"):
            full_url = f"http://{external_host}{view_url}"
        else:
            full_url = view_url
        print(json.dumps({
            "url": full_url,
            "id": result.get("id", ""),
            "internal_url": f"{RENDER_SERVER}{view_url}",
        }))
    else:
        print(json.dumps({"file": output_path}))

    # Cleanup temp file
    if not args.output and os.path.exists(output_path):
        try:
            os.unlink(output_path)
        except Exception:
            pass


if __name__ == "__main__":
    main()
