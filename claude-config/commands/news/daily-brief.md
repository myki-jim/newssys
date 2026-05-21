Generate a daily news brief using only the last 7 days. If `$ARGUMENTS` is provided, use it as a topic filter.

```bash
END_DATE=$(date -u +%Y-%m-%dT%H:%M:%S)
START_DATE=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S)
```

1. Get dashboard stats: `curl -s "http://backend:8000/api/v1/dashboard/stats" | jq '.data'`
2. Get keyword cloud: `curl -s "http://backend:8000/api/v1/dashboard/keywords/cloud?period=today&limit=30" | jq '.data'`
3. Get recent activity: `curl -s "http://backend:8000/api/v1/dashboard/recent-activity?limit=20" | jq '.data'`
4. Search articles (last 7 days, titles only): `curl -s "http://backend:8000/api/v1/articles?page_size=20&sort_by=publish_time&sort_order=desc&publish_start=$START_DATE&publish_end=$END_DATE" | jq '.data.items[].title'`
5. If topic filter: add `&keyword=$ARGUMENTS` to the article search
6. Pick top 5-8 most relevant articles by title, fetch full content
7. Get trends: `curl -s "http://backend:8000/api/v1/dashboard/stats/trends" | jq '.data'`

Present as a structured daily brief:
- **Headline**: most important story
- **Stats at a Glance**: total articles, sources, reports
- **Top Stories**: 3-5 stories with summaries and article IDs
- **Trending Topics**: keyword analysis
- **System Health**: crawl status, pending items
