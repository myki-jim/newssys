#!/usr/bin/env python3
"""
Publish HTML content to render-server with validation.

Usage:
    python3 publish_html.py --file report.html [--title "Report Title"]
    python3 publish_html.py --title "Report" < report.html

Checks render-server health, validates content, uploads HTML, returns URLs.
"""
import sys
import os
import json
import argparse
import urllib.request
import urllib.parse

RENDER_SERVER = os.environ.get("RENDER_SERVER_URL", "http://render-server:8000")
EXTERNAL_HOST = os.environ.get("EXTERNAL_HOST", "192.168.20.26:8081")
MIN_CONTENT_BYTES = 100


def check_health() -> bool:
    """Check render-server is reachable."""
    try:
        req = urllib.request.Request(f"{RENDER_SERVER}/api/list", method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Render server health check FAILED: {e}", file=sys.stderr)
        return False


def validate_content(content: str) -> bool:
    """Check content has meaningful text."""
    if not content or not content.strip():
        print("ERROR: Content is empty", file=sys.stderr)
        return False

    # Strip HTML tags for length check
    import re
    text = re.sub(r'<[^>]+>', '', content).strip()
    if len(text.encode('utf-8')) < MIN_CONTENT_BYTES:
        print(f"ERROR: Content too short ({len(text.encode('utf-8'))} bytes, min {MIN_CONTENT_BYTES})", file=sys.stderr)
        return False

    return True


def publish(title: str, content: str) -> dict:
    """Upload HTML content to render-server, return result dict."""
    data = urllib.parse.urlencode({
        "title": title,
        "content": content,
        "content_type": "html",
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
    parser = argparse.ArgumentParser(description="Publish HTML to render-server")
    parser.add_argument("--file", help="HTML file path (default: stdin)")
    parser.add_argument("--title", default="Report", help="Report title")
    parser.add_argument("--skip-health-check", action="store_true", help="Skip render health check")
    args = parser.parse_args()

    # 1. Health check
    if not args.skip_health_check:
        if not check_health():
            print(json.dumps({"success": False, "error": "Render server unreachable"}))
            sys.exit(1)
        print("Render server: OK", file=sys.stderr)

    # 2. Read input
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
        if not args.title or args.title == "Report":
            # Try to extract title from HTML <title> tag
            import re
            m = re.search(r'<title>([^<]+)</title>', content)
            if m:
                args.title = m.group(1).strip()
    else:
        content = sys.stdin.read()

    # 3. Validate
    if not validate_content(content):
        print(json.dumps({"success": False, "error": "Content validation failed"}))
        sys.exit(1)
    print(f"Content: {len(content)} bytes, valid", file=sys.stderr)

    # 4. Publish
    result = publish(args.title, content)
    if "error" in result:
        print(json.dumps({"success": False, "error": result["error"]}))
        sys.exit(1)

    sid = result.get("id", "")
    view_url = f"http://{EXTERNAL_HOST}/view/{sid}"
    pdf_url = f"http://{EXTERNAL_HOST}/view/{sid}/pdf"

    output = {
        "success": True,
        "id": sid,
        "title": args.title,
        "view_url": view_url,
        "pdf_url": pdf_url,
    }
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
