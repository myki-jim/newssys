# Newssys 2.0 部署指南

## 快速部署

### 1. 准备文件

确保以下文件在同一目录：
```
newssys/
├── deploy.sh                 # 一键部署脚本
├── docker-images/
│   ├── backend-image.tar     # 后端镜像
│   └── frontend-image.tar    # 前端镜像
└── newssys.db (可选)         # 现有数据库
```

### 2. 运行部署脚本

```bash
./deploy.sh
```

### 3. 按提示输入配置

脚本会依次要求输入：
- **OPENAI_API_KEY**: OpenAI API 密钥（必需）
- **OPENAI_BASE_URL**: API 地址（默认：https://api.openai.com/v1）
- **OPENAI_MODEL**: 模型名称（默认：gpt-4o-mini）
- **前端端口**: 前端访问端口（默认：3000）
- **后端端口**: 后端 API 端口（默认：8000）
- **数据库文件**: 是否导入现有数据库（可选）

### 4. 访问系统

部署完成后访问：
- 前端：http://localhost:3000
- 后端：http://localhost:8000
- API 文档：http://localhost:8000/api/docs

部署后会同时启动两个后端容器：
- `newssys-backend`: 只提供 API
- `newssys-worker`: 只运行调度器和后台任务轮询

两个容器默认每 24 小时轮换重启一次；如果健康检查连续失败，会主动退出并由 Docker 自动拉起。

---

## 配置说明

### OpenAI 配置

| 配置项 | 说明 | 示例 |
|--------|------|------|
| OPENAI_API_KEY | API 密钥 | sk-xxxxxxxxxxxx |
| OPENAI_BASE_URL | API 地址 | https://api.openai.com/v1 |
| OPENAI_MODEL | 模型名称 | gpt-4o-mini, gpt-4o |

### 使用其他 AI 服务

如果使用兼容 OpenAI 的其他服务（如 Azure OpenAI、国内中转），只需修改 `OPENAI_BASE_URL`：

```bash
# Azure OpenAI
OPENAI_BASE_URL=https://your-resource.openai.azure.com/

# 国内中转服务
OPENAI_BASE_URL=https://api.your-proxy.com/v1
```

---

## 常用命令

### 服务管理

```bash
# 查看服务状态
docker ps | grep newssys

# 查看后端日志
docker logs -f newssys-backend

# 查看 worker 日志
docker logs -f newssys-worker

# 查看前端日志
docker logs -f newssys-frontend

# 停止服务
docker stop newssys-backend newssys-worker newssys-frontend

# 启动服务
docker start newssys-backend newssys-worker newssys-frontend

# 重启服务
docker restart newssys-backend newssys-worker newssys-frontend

# 删除服务（数据保留）
docker stop newssys-backend newssys-worker newssys-frontend
docker rm newssys-backend newssys-worker newssys-frontend
```

### 数据库管理

```bash
# 备份数据库
docker cp newssys-backend:/data/newssys-pro.db ./backup-$(date +%Y%m%d).db

# 恢复数据库
docker cp ./backup.db newssys-backend:/data/newssys-pro.db
docker restart newssys-backend

# 查看数据库位置
docker volume inspect newssys-data

# 直接访问数据库
docker exec -it newssys-backend sqlite3 /data/newssys-pro.db
```

---

## 故障排除

### 1. 服务无法启动

```bash
# 查看详细日志
docker logs newssys-backend
docker logs newssys-worker
docker logs newssys-frontend

# 检查端口占用
lsof -i :3000
lsof -i :8000
```

### 2. AI 功能不可用

检查环境变量是否正确：
```bash
docker exec newssys-backend env | grep OPENAI
```

### 3. 数据库错误

```bash
# 检查数据库文件
docker exec newssys-backend ls -lh /data/

# 重新导入数据库
docker cp your-db.db newssys-backend:/data/newssys-pro.db
docker restart newssys-backend
```

### 4. 完全重装

```bash
# 停止并删除容器
docker stop newssys-backend newssys-worker newssys-frontend
docker rm newssys-backend newssys-worker newssys-frontend

# 删除数据卷（会清空所有数据）
docker volume rm newssys-data

# 删除网络
docker network rm newssys-network

# 重新运行部署脚本
./deploy.sh
```

---

## 升级系统

### 1. 备份数据

```bash
docker cp newssys-backend:/data/newssys-pro.db ./backup-before-upgrade.db
```

### 2. 停止旧服务

```bash
docker stop newssys-backend newssys-worker newssys-frontend
docker rm newssys-backend newssys-worker newssys-frontend
```

### 3. 加载新镜像

```bash
docker load -i docker-images/backend-image.tar
docker load -i docker-images/frontend-image.tar
```

### 4. 重新启动

```bash
./deploy.sh
```

---

## 目录结构

```
newssys/
├── deploy.sh                    # 一键部署脚本
├── docker-images/               # Docker 镜像
│   ├── backend-image.tar
│   └── frontend-image.tar
├── docker-compose.yml           # Docker Compose 配置
├── Dockerfile.backend           # 后端 Dockerfile
├── Dockerfile.frontend          # 前端 Dockerfile
├── docker/                      # Docker 配置文件
│   └── nginx.conf
├── .env.example                 # 环境变量示例
├── DOCKER_START.md              # Docker 启动说明
└── DEPLOY.md                    # 本文件
```

---

## 系统要求

- Docker 20.10+
- Docker Compose 2.0+（可选）
- 至少 2GB 可用内存
- 至少 5GB 可用磁盘空间

---

## 安全建议

1. **保护 API Key**
   - 不要将 .env 文件提交到版本控制
   - 定期更换 API Key

2. **网络安全**
   - 生产环境建议配置 HTTPS
   - 使用防火墙限制端口访问

3. **数据备份**
   - 定期备份数据库
   - 备份 Docker volume

4. **更新维护**
   - 定期更新镜像
   - 关注安全公告
