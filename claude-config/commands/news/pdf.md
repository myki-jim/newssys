Generate a professional PDF report on `$ARGUMENTS` using the news system framework. Default to last 7 days.

```bash
END_DATE=$(date -u +%Y-%m-%dT%H:%M:%S)
START_DATE=$(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S)
```

1. Search articles (titles first): `curl -s "http://backend:8000/api/v1/articles?keyword=$ARGUMENTS&page_size=20&sort_by=publish_time&sort_order=desc&publish_start=$START_DATE&publish_end=$END_DATE" | jq '.data'`
2. Get dashboard stats for context
3. Read titles, pick top 5-8 articles, fetch full content
4. Write a Python script using `PDFBuilder` from `scripts/pdf_generator.py`
5. Script structure:
   - Title page + date range
   - 一、概述 (executive summary with key stats table)
   - 二、关键发现 (key findings with article references)
   - 三、事件时间线 (chronological event timeline)
   - 四、舆情趋势 (trend analysis)
   - 五、结论与建议 (conclusions)
   - References section with article IDs and URLs
6. Run: `python3 /workspace/report_script.py`
7. Report the output PDF path

Style: h2 for sections, h3 for sub-sections, pi for body, key_value_table for metadata.
