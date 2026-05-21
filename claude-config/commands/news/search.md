Search articles in the news system for `$ARGUMENTS` (keyword).

1. Compute date range:
```bash
END_DATE=$(date -u +%Y-%m-%dT%H:%M:%S)
START_DATE=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S)
```
If time range is specified: adjust START_DATE accordingly (e.g., `-d '30 days ago'` for month).

2. Search articles (titles first):
```bash
curl -s "http://backend:8000/api/v1/articles?keyword=$ARGUMENTS&page_size=20&sort_by=publish_time&sort_order=desc&publish_start=$START_DATE&publish_end=$END_DATE" | jq '.data'
```

3. Summarize: total found, top 10 by relevance — show title, publish_time, source, article ID.
4. Highlight high-value or recent articles.
5. Only fetch full content for articles the user wants to read.

Present in a clean table format.
