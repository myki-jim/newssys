# Newssys 2.0 系统初始化与启动指南

## 环境信息

- **数据库**: 192.168.1.100:3306
- **数据库名**: newssys-pro
- **AI 模型**: deepseek-ai/DeepSeek-V3 (SiliconFlow)

## 一、首次初始化

### 1. 创建数据库

```bash
# 连接到 MySQL 服务器
mysql -h 192.168.1.100 -u root -pjG679322

# 在 MySQL 命令行中执行
CREATE DATABASE IF NOT EXISTS `newssys-pro` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. 执行数据库迁移

```bash
# 方式一：使用初始化脚本（推荐）
python3 scripts/init_database.py

# 方式二：手动执行 SQL
mysql -h 192.168.1.100 -u root -pjG679322 newssys-pro < schema.sql
mysql -h 192.168.1.100 -u root -pjG679322 newssys-pro < migrations/002_schema_stabilization.sql
```

### 3. 注入种子数据

```bash
python3 scripts/seed_sources.py
```

这将注入 3 个哈萨克斯坦新闻源：
- **Kazinform (哈通社)**: https://www.inform.kz/
- **Tengrinews**: https://tengrinews.kz/
- **Kursiv (经济类)**: https://kursiv.kz/

### 4. 运行全链路测试

```bash
python3 scripts/test_pipeline.py
```

测试内容：
1. ✓ Sitemap 探测 - 打印发现的最新 5 条 URL
2. ✓ 解析校验 - 展示标题、Markdown 正文长度、publish_time
3. ✓ AI 预筛选 - DeepSeek-V3 筛选 10 篇文章中的前 3 个核心事件
4. ✓ SSE 连通性 - 验证 SSE 端口流式响应

## 二、启动服务

### 后端启动

```bash
# 开发模式（自动重载）
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn src.api.main:app --workers 4 --host 0.0.0.0 --port 8000
```

### 前端启动

```bash
cd frontend

# 首次运行需要安装依赖
npm install

# 开发模式
npm run dev

# 生产构建
npm run build
npm run preview
```

## 三、验证部署

### 1. 健康检查

```bash
curl http://localhost:8000/api/health
```

预期响应：
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "version": "2.0.0",
    "service": "newssys-api"
  }
}
```

### 2. API 文档

浏览器访问：
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

### 3. 前端访问

浏览器访问：
- 前端界面: http://localhost:5173

## 四、第一个可测试的 API 端点

### 获取采集源列表

```bash
curl http://localhost:8000/api/v1/sources
```

### 调试解析器配置

```bash
curl -X POST "http://localhost:8000/api/v1/sources/debug/parser" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.inform.kz/",
    "config": {
      "title_selector": "h1",
      "content_selector": "article",
      "encoding": "utf-8"
    }
  }'
```

### 触发单条文章采集

```bash
curl -X POST "http://localhost:8000/api/v1/articles/fetch/single" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.inform.kz/some-article"
  }'
```

### 生成报告（SSE 流式）

```bash
curl -N -X POST "http://localhost:8000/api/v1/reports/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "哈萨克斯坦今日动态",
    "time_range": "week",
    "max_articles": 10
  }'
```

## 五、常见问题

### Q: 数据库连接失败

**A**: 检查以下几点：
1. MySQL 服务器是否运行在 192.168.1.100:3306
2. 防火墙是否允许 3306 端口
3. 密码是否正确
4. 用户是否有远程访问权限

```sql
-- 授予远程访问权限（在 MySQL 中执行）
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' IDENTIFIED BY 'jG679322';
FLUSH PRIVILEGES;
```

### Q: AI API 调用失败

**A**: 检查 API Key 是否有效：
```bash
curl -X POST "https://api.siliconflow.cn/v1/chat/completions" \
  -H "Authorization: Bearer sk-pejwAAhbKCYdHmqQfXGKLWb8s9c4Bbmz8JtPqVBXfzDm7Rk" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-ai/DeepSeek-V3",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 10
  }'
```

### Q: 前端无法连接后端

**A**: 检查 CORS 配置和代理设置：
1. 后端 CORS_ORIGINS 是否包含前端地址
2. 前端 vite.config.ts 中的 proxy 配置是否正确

## 六、目录结构

```
newssys/
├── .env                          # 环境配置
├── schema.sql                    # 初始数据库结构
├── migrations/
│   └── 002_schema_stabilization.sql  # 稳固化迁移
├── scripts/
│   ├── init_database.py          # 数据库初始化脚本
│   ├── seed_sources.py           # 种子数据注入
│   └── test_pipeline.py          # 全链路测试
├── src/
│   ├── api/                      # FastAPI 接口层
│   ├── core/                     # 核心模块（配置、模型、数据库）
│   ├── services/                 # 业务逻辑层
│   └── repository/               # 数据访问层
└── frontend/                     # React 前端
    └── src/
        ├── components/           # UI 组件
        ├── pages/                # 页面组件
        └── services/             # API 客户端
```

## 七、日志位置

日志文件位置：`logs/newssys.log`

查看实时日志：
```bash
tail -f logs/newssys.log
```
