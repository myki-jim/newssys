---
name: event-correlation
description: >
  Use whenever the user asks to correlate events, find patterns, analyze timelines,
  discover connections between incidents, or trace event chains. Triggered by
  keywords: correlation, timeline, pattern, connect events, event chain, what happened,
  sequence, cause and effect, related events, incident analysis.
version: 1.0.0
allowed-tools: [Bash, WebFetch, WebSearch]
user-invocable: true
---

# Event Correlation & Timeline Analysis

Discover connections between events, build timelines, and identify patterns across news articles and open sources.

## Core Workflows

### 1. Timeline Construction
1. Search articles for the subject: `curl -s "http://backend:8000/api/v1/articles?keyword=<subject>&page_size=50&sort_by=publish_time&sort_order=asc"`
2. Get timeline data: `curl -s "http://backend:8000/api/v1/dashboard/timeline?days=30"`
3. For each article, extract: date, location, actors, action, outcome
4. Sort chronologically, mark key turning points

### 2. Event Correlation
For each pair of events, assess:
- **Temporal proximity**: how close in time
- **Geographic proximity**: same location or region
- **Actor overlap**: same people or organizations involved
- **Causal chain**: does one event logically lead to another
- **Pattern match**: similar MO, same type of incident

### 3. Pattern Detection
- **Frequency analysis**: is this event rate normal or anomalous (use dashboard stats for baseline)
- **Cluster detection**: do events concentrate in time/location/actor
- **Escalation patterns**: is frequency or severity increasing
- **Copycat detection**: similar events following a high-profile incident
- **Seasonal patterns**: recurring at specific times

### 4. Causal Chain Analysis
```
Event A (date, location, actors)
  ↓ [mechanism: how A led to B]
Event B (date, location, actors)
  ↓ [mechanism]
Event C (date, location, actors)
```
For each link, document:
- Evidence from articles (direct statement or inference)
- Alternative explanations
- Confidence level

### 5. Multi-Source Verification
- Search internal news system for corroborating articles
- Use web search for external coverage
- Compare timelines across sources
- Flag contradictions and single-source claims

### 6. Dashboard Integration
- Use keyword cloud to identify trending terms: `curl -s "http://backend:8000/api/v1/dashboard/keywords/cloud?period=week&limit=50"`
- Use trend data: `curl -s "http://backend:8000/api/v1/dashboard/stats/trends"`
- Cross-reference with top sources for bias assessment

### 7. Predictive Analysis
Based on patterns found:
- What typically happens next in similar event chains
- Risk factors present for escalation
- Historical precedents from similar cases
- Confidence level for predictions

## Output Format
1. **Executive Summary**: 2-3 sentence overview of the event chain
2. **Timeline**: chronological event list with dates, locations, actors, sources
3. **Correlation Matrix**: which events are related and how (markdown table)
4. **Causal Diagram**: ASCII art or Mermaid flowchart showing event chain
5. **Pattern Analysis**: identified patterns, anomalies, trends
6. **Key Actors**: people/organizations appearing across multiple events
7. **Source Map**: article IDs and URLs supporting each claim
8. **Confidence Assessment**: per-link and overall confidence level

## Example: Event Chain

```
2024-01-15 | Company X announces expansion | City A | CEO Smith | [Article #1234]
    ↓ [regulatory environment]
2024-01-20 | Local government protests expansion | City A | Mayor Jones | [Article #1256]
    ↓ [public pressure]
2024-02-01 | Company X withdraws application | City A | [Article #1300]
```
