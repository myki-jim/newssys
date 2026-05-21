Generate a comprehensive report on `$ARGUMENTS` (topic or keyword). Default to last 7 days.

```bash
END_DATE=$(date -u +%Y-%m-%dT%H:%M:%S)
START_DATE=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S)
```

1. Search articles (titles first): `curl -s "http://backend:8000/api/v1/articles?keyword=$ARGUMENTS&page_size=30&sort_by=publish_time&sort_order=desc&publish_start=$START_DATE&publish_end=$END_DATE" | jq '.data'`
2. Read titles, pick top 10 most relevant
3. Fetch full content only for those 10
4. Get timeline: `curl -s "http://backend:8000/api/v1/dashboard/timeline?days=7" | jq '.data'`
5. Enrich with web search: `curl -s "http://backend:8000/api/v1/search?query=$ARGUMENTS&max_results=10" | jq '.data'`
6. Find similar articles for key pieces

Present as structured report:
- Executive Summary
- Timeline of Events
- Key Actors & Organizations
- Article Analysis (with source article IDs)
- External Context (web results)
- Trends & Patterns
- Sources
