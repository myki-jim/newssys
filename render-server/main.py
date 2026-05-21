"""Render Server — 通用内容展示服务"""
import base64
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request, Form, Body
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel
import markdown as md_lib

app = FastAPI(title="Render Server", version="1.1.0")

CONTENT_DIR = Path(os.environ.get("RENDER_DATA_DIR", "/data/renders"))
CONTENT_DIR.mkdir(parents=True, exist_ok=True)


# ── Pydantic model for JSON body ────────────────────────────────────────────
class PublishBody(BaseModel):
    title: str = "Untitled"
    content: str = ""
    content_type: str = "html"


# ── HTML templates ──────────────────────────────────────────────────────────
LIST_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Render Server — 内容列表</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", sans-serif;
    background: #f5f7fa; color: #2d3748; line-height: 1.6;
  }}
  header {{
    background: linear-gradient(135deg, #1a365d 0%, #2b6cb0 100%);
    color: #fff; padding: 32px 24px; text-align: center;
  }}
  header h1 {{ font-size: 24px; font-weight: 700; }}
  header p {{ font-size: 13px; opacity: 0.7; margin-top: 6px; }}
  .container {{ max-width: 960px; margin: 0 auto; padding: 24px; }}
  .toolbar {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 16px; flex-wrap: wrap; gap: 8px;
  }}
  .toolbar .count {{ font-size: 14px; color: #718096; }}
  .toolbar input {{
    padding: 8px 12px; border: 1px solid #cbd5e0; border-radius: 6px;
    font-size: 14px; width: 240px; outline: none;
  }}
  .toolbar input:focus {{ border-color: #2b6cb0; box-shadow: 0 0 0 2px rgba(43,108,176,0.15); }}
  table {{
    width: 100%; border-collapse: collapse; background: #fff;
    border-radius: 10px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }}
  th, td {{ padding: 12px 16px; text-align: left; }}
  th {{ background: #f7fafc; font-weight: 600; font-size: 13px; color: #4a5568; border-bottom: 2px solid #e2e8f0; }}
  td {{ border-bottom: 1px solid #edf2f7; font-size: 14px; }}
  tr:hover td {{ background: #f7fafc; }}
  td.title {{ font-weight: 500; }}
  td.title a {{ color: #2b6cb0; text-decoration: none; }}
  td.title a:hover {{ text-decoration: underline; }}
  .badge {{
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 11px; font-weight: 600; text-transform: uppercase;
  }}
  .badge-html {{ background: #c6f6d5; color: #22543d; }}
  .badge-pdf {{ background: #fed7d7; color: #9b2c2c; }}
  .badge-md {{ background: #feebc8; color: #7c2d12; }}
  .empty {{
    text-align: center; padding: 60px 20px; color: #a0aec0;
  }}
  .empty .icon {{ font-size: 48px; margin-bottom: 16px; }}
  .footer {{ text-align: center; padding: 24px; font-size: 12px; color: #a0aec0; }}
  @media (max-width: 640px) {{
    th, td {{ padding: 10px 12px; font-size: 13px; }}
    .toolbar input {{ width: 100%; }}
  }}
</style>
</head>
<body>
<header>
  <h1>Render Server</h1>
  <p>已发布内容列表</p>
</header>
<div class="container">
  <div class="toolbar">
    <span class="count" id="stats"></span>
    <input type="text" id="filter" placeholder="搜索标题..." oninput="filterRows()">
  </div>
  <table id="file-table">
    <thead>
      <tr><th>标题</th><th>类型</th><th>发布时间</th><th>操作</th></tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>
  <div class="empty" id="empty-msg" style="display:none">
    <div class="icon">📄</div>
    <p>暂无已发布内容</p>
  </div>
</div>
<div class="footer">Render Server v1.1.0</div>
<script>
  async function load() {{
    const resp = await fetch('/api/list');
    const items = await resp.json();
    const tbody = document.getElementById('tbody');
    const empty = document.getElementById('empty-msg');
    const stats = document.getElementById('stats');
    if (items.length === 0) {{
      empty.style.display = 'block';
      document.getElementById('file-table').style.display = 'none';
      stats.textContent = '';
      return;
    }}
    empty.style.display = 'none';
    document.getElementById('file-table').style.display = '';
    stats.textContent = '共 ' + items.length + ' 项';
    const badges = {{html:'HTML', pdf:'PDF', md:'Markdown'}};
    tbody.innerHTML = items.map(item => {{
      const ft = item.file_type || item.content_type || 'html';
      const badgeClass = 'badge-' + (ft === 'pdf' ? 'pdf' : ft === 'markdown' ? 'md' : 'html');
      const badgeLabel = badges[ft] || ft.toUpperCase();
      return '<tr>' +
        '<td class="title"><a href="/view/' + item.id + '">' + esc(item.title) + '</a></td>' +
        '<td><span class="badge ' + badgeClass + '">' + badgeLabel + '</span></td>' +
        '<td>' + esc(item.created_at || '') + '</td>' +
        '<td><a href="/raw/' + item.id + '" download>下载</a></td>' +
      '</tr>';
    }}).join('');
  }}
  function esc(s) {{ return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }}
  function filterRows() {{
    const q = document.getElementById('filter').value.toLowerCase();
    const rows = document.querySelectorAll('#tbody tr');
    rows.forEach(r => r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none');
  }}
  load();
</script>
</body>
</html>"""

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", sans-serif;
    background: #f5f7fa; color: #2d3748; line-height: 1.8;
  }}
  .container {{ max-width: 900px; margin: 0 auto; padding: 40px 24px; }}
  header {{
    background: linear-gradient(135deg, #1a365d 0%, #2b6cb0 100%);
    color: #fff; padding: 48px 24px; text-align: center;
  }}
  header h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 8px; }}
  header .meta {{ font-size: 13px; opacity: 0.75; }}
  .content {{
    background: #fff; border-radius: 12px; padding: 40px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-top: -20px;
  }}
  .content h1 {{ font-size: 24px; color: #1a365d; margin: 28px 0 12px; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }}
  .content h2 {{ font-size: 20px; color: #2b6cb0; margin: 24px 0 10px; }}
  .content h3 {{ font-size: 17px; color: #3182ce; margin: 20px 0 8px; }}
  .content p {{ margin: 10px 0; }}
  .content ul, .content ol {{ margin: 8px 0 8px 24px; }}
  .content li {{ margin: 4px 0; }}
  .content table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
  .content th, .content td {{ border: 1px solid #cbd5e0; padding: 8px 12px; text-align: left; }}
  .content th {{ background: #f7fafc; font-weight: 600; color: #1a365d; }}
  .content blockquote {{
    border-left: 3px solid #2b6cb0; padding: 8px 16px; margin: 12px 0;
    background: #f7fafc; color: #4a5568;
  }}
  .content code {{ background: #edf2f7; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
  .content pre {{ background: #1a202c; color: #e2e8f0; padding: 16px; border-radius: 8px; overflow-x: auto; margin: 12px 0; }}
  .content pre code {{ background: none; padding: 0; color: inherit; }}
  .content a {{ color: #2b6cb0; }}
  .content img {{ max-width: 100%; border-radius: 8px; }}
  .footer {{ text-align: center; padding: 24px; font-size: 12px; color: #a0aec0; }}
  .pdf-container {{ width: 100%; height: 85vh; border: none; border-radius: 8px; }}
  @media (max-width: 640px) {{
    .container {{ padding: 16px; }}
    .content {{ padding: 24px; }}
    header {{ padding: 32px 16px; }}
    header h1 {{ font-size: 22px; }}
  }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div class="meta">生成时间: {created_at}</div>
</header>
<div class="container">
  <div class="content">
{body}
  </div>
</div>
<div class="footer">Powered by Render Server</div>
</body>
</html>"""

PDF_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f7fa; }}
  header {{
    background: linear-gradient(135deg, #1a365d 0%, #2b6cb0 100%);
    color: #fff; padding: 32px 24px; text-align: center;
  }}
  header h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 6px; }}
  header .meta {{ font-size: 13px; opacity: 0.75; }}
  iframe {{ width: 100%; height: calc(100vh - 130px); border: none; }}
  .footer {{ text-align: center; padding: 12px; font-size: 12px; color: #a0aec0; }}
  .actions {{ text-align: center; padding: 12px; }}
  .actions a {{
    display: inline-block; padding: 8px 20px; background: #2b6cb0; color: #fff;
    border-radius: 6px; text-decoration: none; font-size: 14px;
  }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div class="meta">生成时间: {created_at}</div>
</header>
<div class="actions"><a href="/raw/{id}" download>下载 PDF</a></div>
<iframe src="/raw/{id}" class="pdf"></iframe>
<div class="footer">Powered by Render Server</div>
</body>
</html>"""


def make_slug(title: str) -> str:
    h = hashlib.md5(f"{title}{uuid.uuid4()}".encode()).hexdigest()[:10]
    return h


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    """文件列表页"""
    return HTMLResponse(LIST_PAGE)


@app.post("/api/publish")
async def publish(request: Request):
    """发布内容 (支持 JSON body 和 form data)"""
    ct = request.headers.get("content-type", "")

    if "application/json" in ct:
        body = await request.json()
        title = body.get("title", "Untitled")
        content = body.get("content", "")
        content_type = body.get("content_type", "html")
    else:
        form = await request.form()
        title = form.get("title", "Untitled")
        content = form.get("content", "")
        content_type = form.get("content_type", "html")

    sid = make_slug(title)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    meta = {"id": sid, "title": title, "content_type": content_type, "created_at": now}
    meta_path = CONTENT_DIR / f"{sid}.meta.json"

    if content_type == "pdf_base64":
        try:
            pdf_data = base64.b64decode(content)
        except Exception:
            return JSONResponse({"error": "Invalid base64 content"}, status_code=400)
        pdf_path = CONTENT_DIR / f"{sid}.pdf"
        pdf_path.write_bytes(pdf_data)
        meta["file_type"] = "pdf"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False))
        return {"url": f"/view/{sid}", "id": sid}

    if content_type == "pdf_path":
        src = Path(content)
        if not src.exists():
            return JSONResponse({"error": f"File not found: {content}"}, status_code=400)
        pdf_path = CONTENT_DIR / f"{sid}.pdf"
        pdf_path.write_bytes(src.read_bytes())
        meta["file_type"] = "pdf"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False))
        return {"url": f"/view/{sid}", "id": sid}

    if content_type == "markdown":
        body_html = md_lib.markdown(
            content, extensions=["tables", "fenced_code", "codehilite", "nl2br"]
        )
    else:
        body_html = content

    page = PAGE_TEMPLATE.format(title=title, created_at=now, body=body_html)
    html_path = CONTENT_DIR / f"{sid}.html"
    html_path.write_text(page, encoding="utf-8")
    meta["file_type"] = "html"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False))
    return {"url": f"/view/{sid}", "id": sid}


@app.get("/view/{sid}")
async def view(sid: str):
    """查看已发布的内容"""
    html_path = CONTENT_DIR / f"{sid}.html"
    pdf_path = CONTENT_DIR / f"{sid}.pdf"
    meta_path = CONTENT_DIR / f"{sid}.meta.json"

    if not meta_path.exists():
        return HTMLResponse("<h1>404 — 内容不存在</h1>", status_code=404)

    meta = json.loads(meta_path.read_text())

    if pdf_path.exists():
        page = PDF_PAGE.format(
            title=meta.get("title", "PDF"),
            created_at=meta.get("created_at", ""),
            id=sid,
        )
        return HTMLResponse(page)

    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))

    return HTMLResponse("<h1>404 — 内容文件缺失</h1>", status_code=404)


@app.get("/raw/{sid}")
async def raw(sid: str):
    """原始文件下载"""
    pdf_path = CONTENT_DIR / f"{sid}.pdf"
    html_path = CONTENT_DIR / f"{sid}.html"
    if pdf_path.exists():
        return FileResponse(pdf_path, media_type="application/pdf")
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    return HTMLResponse("<h1>404</h1>", status_code=404)


@app.get("/api/list")
async def list_renders():
    """列出所有已发布内容"""
    items = []
    for f in sorted(CONTENT_DIR.glob("*.meta.json"), key=os.path.getmtime, reverse=True):
        meta = json.loads(f.read_text())
        items.append(meta)
    return items[:50]
