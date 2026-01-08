import { useQuery } from "@tanstack/react-query"
import { dashboardApi } from "@/services/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  FileText,
  Globe,
  AlertCircle,
  Activity,
  HardDrive,
} from "lucide-react"
import { formatFileSize } from "@/lib/utils"
import { cn } from "@/lib/utils"
import { Link } from "react-router-dom"
import { KeywordCloudGrid } from "@/components/dashboard/KeywordCloud"

export function DashboardPage() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: () => dashboardApi.getStats(),
  })

  const { data: health } = useQuery({
    queryKey: ["dashboard", "health"],
    queryFn: () => dashboardApi.getHealth(),
    refetchInterval: 30000, // 每 30 秒刷新
  })

  const { data: timeline } = useQuery({
    queryKey: ["dashboard", "timeline"],
    queryFn: () => dashboardApi.getTimeline(7),
  })

  const { data: topSources } = useQuery({
    queryKey: ["dashboard", "topSources"],
    queryFn: () => dashboardApi.getTopSources(5, 7),
  })

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent mx-auto" />
          <p className="mt-4 text-sm text-muted-foreground">加载中...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">仪表盘</h1>
        <p className="text-muted-foreground">
          系统概览与实时监控
        </p>
      </div>

      {/* 统计卡片 */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">采集源总数</CardTitle>
            <Globe className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats?.active_sources || 0} / {stats?.total_sources || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              活跃 / 总数
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">文章总数</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_articles || 0}</div>
            <p className="text-xs text-muted-foreground">
              今日新增: {stats?.today_articles || 0}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">失败文章</CardTitle>
            <AlertCircle className="h-4 w-4 text-destructive" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.failed_articles || 0}</div>
            <p className="text-xs text-muted-foreground">
              需要重试
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">存储使用</CardTitle>
            <HardDrive className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatFileSize((stats?.storage_used_mb || 0) * 1024 * 1024)}
            </div>
            <p className="text-xs text-muted-foreground">
              数据库大小
            </p>
          </CardContent>
        </Card>
      </div>

      {/* 系统健康状态 */}
      {health && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              系统健康状态
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <div className={cn(
                "flex h-3 w-3 rounded-full",
                health.status === "healthy" && "bg-green-500",
                health.status === "warning" && "bg-yellow-500",
                health.status === "critical" && "bg-red-500"
              )} />
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <span className="font-medium">
                    {health.status === "healthy" && "系统正常"}
                    {health.status === "warning" && "需要注意"}
                    {health.status === "critical" && "严重问题"}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {new Date().toLocaleString("zh-CN")}
                  </span>
                </div>
                {health.issues.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {health.issues.map((issue, i) => (
                      <li key={i} className="text-sm text-muted-foreground">
                        • {issue}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">待处理文章: </span>
                <span className="font-medium">{health.metrics.pending_articles}</span>
              </div>
              <div>
                <span className="text-muted-foreground">重试队列: </span>
                <span className="font-medium">{health.metrics.retry_queue}</span>
              </div>
              <div>
                <span className="text-muted-foreground">24h 失败率: </span>
                <span className={cn(
                  "font-medium",
                  health.metrics.failure_rate_24h > 20 && "text-destructive"
                )}>
                  {health.metrics.failure_rate_24h}%
                </span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 热门采集源 */}
      {topSources && topSources.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>热门采集源（本周）</CardTitle>
              <Button variant="outline" size="sm" asChild>
                <Link to="/sources">查看全部</Link>
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {topSources.map((source) => (
                <div key={source.source_id} className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{source.site_name}</span>
                      <span className="text-xs text-muted-foreground">
                        {source.total_articles} 篇
                      </span>
                    </div>
                    <div className="mt-1 h-2 w-full rounded-full bg-muted">
                      <div
                        className="h-2 rounded-full bg-primary"
                        style={{ width: `${source.success_rate}%` }}
                      />
                    </div>
                  </div>
                  <div className="ml-4 text-sm">
                    <span className="text-muted-foreground">成功率: </span>
                    <span className="font-medium">{source.success_rate}%</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 关键词词云 */}
      <Card>
        <CardHeader>
          <CardTitle>关键词词云</CardTitle>
        </CardHeader>
        <CardContent>
          <KeywordCloudGrid />
        </CardContent>
      </Card>

      {/* 快捷操作 */}
      <Card>
        <CardHeader>
          <CardTitle>快捷操作</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button asChild>
            <Link to="/sources">添加采集源</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/articles">批量重试失败文章</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/reports">生成新报告</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/search">联网搜索</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
