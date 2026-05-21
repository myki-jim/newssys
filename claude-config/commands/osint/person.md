Investigate a person: `$ARGUMENTS` (name, email, username, or phone).

1. Search news system (last 7 days, titles first):
```bash
END_DATE=$(date -u +%Y-%m-%dT%H:%M:%S)
START_DATE=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S)
curl -s "http://backend:8000/api/v1/articles?keyword=$ARGUMENTS&page_size=20&sort_by=publish_time&sort_order=desc&publish_start=$START_DATE&publish_end=$END_DATE" | jq '.data'
```
2. Read titles, pick relevant articles, fetch full content
3. Web search for public profiles and mentions
4. If email: check domain WHOIS, MX records, breach databases
5. If username: cross-platform search (GitHub, Twitter, Reddit, LinkedIn)
6. Cross-reference all findings

Present as structured person dossier with:
- Identity summary, online presence, news mentions, risk indicators, sources
