Build a knowledge graph for `$ARGUMENTS` (person, organization, or topic). Default to last 7 days.

```bash
END_DATE=$(date -u +%Y-%m-%dT%H:%M:%S)
START_DATE=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S)
```

1. Search news system: `curl -s "http://backend:8000/api/v1/articles?keyword=$ARGUMENTS&page_size=30&sort_by=publish_time&sort_order=desc&publish_start=$START_DATE&publish_end=$END_DATE" | jq '.data'`
2. Read titles, pick top 15 articles, fetch full content
3. Extract: people, organizations, locations, events, dates
4. Map relationships between all entities
5. Build Mermaid graph visualization
6. Identify central nodes, bridges, clusters

Output:
- Entity list by type
- Relationship table
- Mermaid graph
- Key insights about the network
