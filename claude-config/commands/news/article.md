Get full detail for article `$ARGUMENTS` (ID number):
1. `curl -s "http://backend:8000/api/v1/articles/$ARGUMENTS" | jq '.data'`
2. Show: title, author, publish_time, source, full content, status, score
3. Show similar articles: `curl -s "http://backend:8000/api/v1/articles/$ARGUMENTS/similar?limit=5" | jq '.data.items'`

Present article content clearly with metadata header.
