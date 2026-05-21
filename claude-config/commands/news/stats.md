Show news system statistics and health overview.

1. Main stats: `curl -s "http://backend:8000/api/v1/dashboard/stats" | jq '.data'`
2. Health check: `curl -s "http://backend:8000/api/v1/dashboard/health" | jq '.data'`
3. Scheduler status: `curl -s "http://backend:8000/api/v1/scheduler/status" | jq '.data'`
4. Task stats: `curl -s "http://backend:8000/api/v1/tasks/stats/summary" | jq '.data'`
5. Top sources: `curl -s "http://backend:8000/api/v1/dashboard/top-sources?limit=10&days=7" | jq '.data'`
6. Keyword trends: `curl -s "http://backend:8000/api/v1/dashboard/stats/trends" | jq '.data'`

Present as a clean dashboard summary with tables.
