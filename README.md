# Newssys

## 本地运行

系统现在是六进程结构：
- `api`: 只提供 HTTP 接口
- `scheduler worker`: 只负责定时任务调度
- `report worker`: 只负责报告生成任务
- `crawl worker`: 只负责爬取相关任务
- `search worker`: 只负责关键词搜索导入任务
- `ai worker`: 只负责 AI 对话 / Agent 对话任务

### 1. 启动 API

```bash
source venv/bin/activate
bash scripts/start_api.sh
```

### 2. 启动调度 worker

```bash
source venv/bin/activate
bash scripts/start_scheduler_worker.sh
```

### 3. 启动报告 worker

```bash
source venv/bin/activate
bash scripts/start_report_worker.sh
```

### 4. 启动爬取 worker

```bash
source venv/bin/activate
bash scripts/start_crawl_worker.sh
```

### 5. 启动搜索 worker

```bash
source venv/bin/activate
bash scripts/start_search_worker.sh
```

### 6. 启动 AI worker

```bash
source venv/bin/activate
bash scripts/start_ai_worker.sh
```

### 7. 健康检查

```bash
python3 scripts/check_api_health.py
WORKER_HEARTBEAT_FILE=/tmp/newssys-scheduler-heartbeat python3 scripts/check_worker_health.py
WORKER_HEARTBEAT_FILE=/tmp/newssys-report-heartbeat python3 scripts/check_worker_health.py
WORKER_HEARTBEAT_FILE=/tmp/newssys-crawl-heartbeat python3 scripts/check_worker_health.py
WORKER_HEARTBEAT_FILE=/tmp/newssys-search-heartbeat python3 scripts/check_worker_health.py
WORKER_HEARTBEAT_FILE=/tmp/newssys-ai-heartbeat python3 scripts/check_worker_health.py
```

## 1Panel 建议

- 应用 1: `bash /path/to/news/scripts/start_api.sh`
- 应用 2: `bash /path/to/news/scripts/start_scheduler_worker.sh`
- 应用 3: `bash /path/to/news/scripts/start_report_worker.sh`
- 应用 4: `bash /path/to/news/scripts/start_crawl_worker.sh`
- 应用 5: `bash /path/to/news/scripts/start_search_worker.sh`
- 应用 6: `bash /path/to/news/scripts/start_ai_worker.sh`
- 存活检测:
  - API: `python3 /path/to/news/scripts/check_api_health.py`
  - scheduler worker: `WORKER_HEARTBEAT_FILE=/tmp/newssys-scheduler-heartbeat python3 /path/to/news/scripts/check_worker_health.py`
  - report worker: `WORKER_HEARTBEAT_FILE=/tmp/newssys-report-heartbeat python3 /path/to/news/scripts/check_worker_health.py`
  - crawl worker: `WORKER_HEARTBEAT_FILE=/tmp/newssys-crawl-heartbeat python3 /path/to/news/scripts/check_worker_health.py`
  - search worker: `WORKER_HEARTBEAT_FILE=/tmp/newssys-search-heartbeat python3 /path/to/news/scripts/check_worker_health.py`
  - ai worker: `WORKER_HEARTBEAT_FILE=/tmp/newssys-ai-heartbeat python3 /path/to/news/scripts/check_worker_health.py`
- 每日重启:
  - 用 1Panel 调度每天执行一次应用重启

## 接口

- API: `http://127.0.0.1:8000`
- API 文档: `http://127.0.0.1:8000/api/docs`
