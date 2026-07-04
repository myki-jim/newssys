---
name: news-system
description: >
  Use whenever the user asks to search articles, read news content, generate reports,
  check system stats, manage crawl sources, or interact with the News Analysis System.
  Triggered by keywords: article, news, report, dashboard, crawl, source, sitemap,
  keyword cloud, trend, stats, schedule, task, search, daily brief.
version: 1.0.0
allowed-tools: [Bash, WebFetch, WebSearch]
user-invocable: true
---

# News Analysis System Integration

The news system API is at `http://backend:8000/api/v1`. Most read endpoints are open. Use `curl -s` for all requests. The API returns `{"success": true, "data": ...}`.

## Time range rule (CRITICAL)

**Always pass time parameters when fetching articles.** Default to last 7 days if user doesn't specify.

```bash
END_DATE=$(date -u +%Y-%m-%dT%H:%M:%S)
START_DATE=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S)
```

**Titles-first:** always fetch article list first (titles only), then decide which articles to read in full.

## API Reference

### Articles (always with time range)
- **List (titles first)**: `curl -s "http://backend:8000/api/v1/articles?page=1&page_size=20&sort_by=publish_time&sort_order=desc&publish_start=$START_DATE&publish_end=$END_DATE"`
- **List with keyword**: add `&keyword=<term>` (URL-encoded)
- **List with source filter**: add `&source_ids=1&source_ids=2`
- **Detail**: `curl -s "http://backend:8000/api/v1/articles/<id>"`
- **Similar**: `curl -s "http://backend:8000/api/v1/articles/<id>/similar?limit=10"`
- **Stats by status**: `curl -s "http://backend:8000/api/v1/articles/stats/by-status"`
- **Create**: `curl -s -X POST "http://backend:8000/api/v1/articles" -H "Content-Type: application/json" -d '{"url":"...","source_id":1}'`

### Reports
- **List**: `curl -s "http://backend:8000/api/v1/reports?limit=20&offset=0"`
- **Detail**: `curl -s "http://backend:8000/api/v1/reports/<id>"`
- **Generate**: `curl -s -X POST "http://backend:8000/api/v1/reports/generate" -H "Content-Type: application/json" -d '{"title":"...","template_id":1,"date_range_start":"...","date_range_end":"..."}'`
- **Templates**: `curl -s "http://backend:8000/api/v1/reports/templates"`
- **Preset time ranges**: `curl -s "http://backend:8000/api/v1/reports/presets/time-ranges"`

### Dashboard & Stats
- **Summary stats**: `curl -s "http://backend:8000/api/v1/dashboard/stats"`
- **Timeline**: `curl -s "http://backend:8000/api/v1/dashboard/timeline?days=7"`
- **Top sources**: `curl -s "http://backend:8000/api/v1/dashboard/top-sources?limit=10&days=7"`
- **Recent activity**: `curl -s "http://backend:8000/api/v1/dashboard/recent-activity?limit=20"`
- **Keyword cloud**: `curl -s "http://backend:8000/api/v1/dashboard/keywords/cloud?period=week&limit=50"`
- **Health**: `curl -s "http://backend:8000/api/v1/dashboard/health"`
- **Trends**: `curl -s "http://backend:8000/api/v1/dashboard/stats/trends"`

### Search
- **Web search**: `curl -s "http://backend:8000/api/v1/search?query=<term>&time_range=w&max_results=20"`
- **Fetch URL**: `curl -s "http://backend:8000/api/v1/search/fetch?url=<url>"`
- **Enrich**: `curl -s -X POST "http://backend:8000/api/v1/search/enrich?query=<term>" -H "Content-Type: application/json" -d '{"local_article_ids":[1,2,3]}'`

### Crawl Sources & Sitemaps
- **List sources**: `curl -s "http://backend:8000/api/v1/sources?page=1&page_size=50"`
- **Source detail**: `curl -s "http://backend:8000/api/v1/sources/<id>"`
- **Source stats**: `curl -s "http://backend:8000/api/v1/sources/stats/all?days=30"`
- **List sitemaps**: `curl -s "http://backend:8000/api/v1/sitemaps?source_id=<id>"`
- **Pending articles**: `curl -s "http://backend:8000/api/v1/sitemaps/pending?limit=50"`

### Tasks & Schedules
- **List tasks**: `curl -s "http://backend:8000/api/v1/tasks?page=1&page_size=20"`
- **Task stats**: `curl -s "http://backend:8000/api/v1/tasks/stats/summary"`
- **List schedules**: `curl -s "http://backend:8000/api/v1/schedules?limit=50"`
- **Scheduler status**: `curl -s "http://backend:8000/api/v1/scheduler/status"`

### Keywords
- **List keywords**: `curl -s "http://backend:8000/api/v1/keywords?is_active=true&limit=100"`

### Auth
- **Login**: `curl -s -X POST "http://backend:8000/api/v1/auth/login" -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}'`

## Core Workflows

### 1. Daily News Brief
```bash
END_DATE=$(date -u +%Y-%m-%dT%H:%M:%S)
START_DATE=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S)
```
1. Get dashboard stats
2. Get keyword cloud (today)
3. Search articles (last 7 days, status=published, page_size=20)
4. **Only read titles from list** — extract top 5-10 interesting ones
5. Fetch full content only for those selected articles
6. Synthesize into brief

### 2. Topic Deep-Dive
1. Compute 7-day date range
2. Search articles with keyword: `curl -s ".../articles?keyword=<term>&page_size=20&sort_by=publish_time&sort_order=desc&publish_start=$START_DATE&publish_end=$END_DATE"`
3. Scan titles, pick relevant ones
4. Fetch full content only for picked articles
5. Find similar articles for key pieces
6. Present timeline + findings + sources

### 3. Source Audit
1. List all sources, get stats
2. Check pending articles per source
3. Review scheduler status
4. Report health summary

### 4. Generate Report
1. List templates, pick appropriate one
2. Get preset time ranges
3. POST to generate report with time range from user or default 7 days
4. Stream progress and fetch final report

## Output Format
- Always cite article IDs, titles, publish dates, and sources
- Present stats in clean tables (markdown)
- For briefs: headline, key stats, top stories with summaries, trending topics
- Link back to system UI: `http://192.168.100.108/articles/<id>`
