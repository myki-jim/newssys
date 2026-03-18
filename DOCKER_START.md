# Newssys 2.0 Docker 部署指南

## 快速启动

### 1. 最简启动（必需：OPENAI_API_KEY）

```bash
OPENAI_API_KEY=sk-your-api-key docker-compose up -d
```

### 2. 完整环境变量启动

```bash
OPENAI_API_KEY=sk-your-api-key \
OPENAI_BASE_URL=https://api.openai.com/v1 \
OPENAI_MODEL=gpt-4o-mini \
FRONTEND_URL=http://localhost:3000 \
BACKEND_PORT=8000 \
FRONTEND_PORT=3000 \
LOG_LEVEL=INFO \
docker-compose up -d
```

### 3. 使用 .env 文件启动

创建 `.env` 文件：
```bash
OPENAI_API_KEY=sk-your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
FRONTEND_URL=http://localhost:3000
BACKEND_PORT=8000
FRONTEND_PORT=3000
LOG_LEVEL=INFO
```

然后启动：
```bash
docker-compose up -d
```

说明：
- `backend` 只提供 API
- `worker` 单独运行定时任务调度器
- 两个容器默认每 24 小时主动轮换重启一次
- 如果健康检查连续失败，容器会主动退出并由 Docker 自动拉起

## 环境变量说明

| 变量 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| OPENAI_API_KEY | 是 | - | OpenAI API 密钥 |
| OPENAI_BASE_URL | 否 | https://api.openai.com/v1 | OpenAI API 地址 |
| OPENAI_MODEL | 否 | gpt-4o-mini | 使用的模型 |
| FRONTEND_URL | 否 | http://localhost:3000 | 前端访问地址 |
| BACKEND_PORT | 否 | 8000 | 后端端口 |
| FRONTEND_PORT | 否 | 3000 | 前端端口 |
| LOG_LEVEL | 否 | INFO | 日志级别 |
| VITE_API_BASE_URL | 否 | /api/v1 | 前端 API 地址 |

## 常用命令

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看日志
docker-compose logs -f

# 单看 worker 日志
docker-compose logs -f worker

# 查看状态
docker-compose ps

# 重新构建镜像
docker-compose build --no-cache

# 清理所有数据（危险）
docker-compose down -v
```

## 访问地址

- 前端: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/api/docs

## 数据持久化

SQLite 数据库存储在 Docker volume 中：
```bash
# 查看数据卷
docker volume ls | grep newssys

# 备份数据库
docker run --rm -v newssys-data:/data -v $(pwd):/backup alpine tar czf /backup/newssys-backup.tar.gz /data

# 恢复数据库
docker run --rm -v newssys-data:/data -v $(pwd):/backup alpine tar xzf /backup/newssys-backup.tar.gz -C /
```
