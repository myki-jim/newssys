import { useState, useEffect, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { sitemapsApi, sourcesApi, tasksApi } from "@/services/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Plus,
  Search,
  RefreshCw,
  Trash2,
  Download,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  FileText,
  Loader2,
  Globe,
  Network,
} from "lucide-react"
import { formatDateTime } from "@/lib/utils"
import type { Sitemap, PendingArticle, CrawlSource, Task } from "@/types"

export function SitemapsPage() {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedSource, setSelectedSource] = useState<number | null>(null)
  const [addSitemapOpen, setAddSitemapOpen] = useState(false)
  const [newSitemapUrl, setNewSitemapUrl] = useState("")
  const [newSitemapSourceId, setNewSitemapSourceId] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState<"sitemaps" | "pending">("sitemaps")
  const [pendingPage, setPendingPage] = useState(1)
  const pendingPageSize = 50

  // 获取源列表
  const { data: sourcesData } = useQuery({
    queryKey: ["sources"],
    queryFn: () => sourcesApi.list({ page: 1, page_size: 100 }),
  })

  // 获取 Sitemap 列表
  const { data: sitemaps, isLoading: sitemapsLoading, refetch: refetchSitemaps } = useQuery({
    queryKey: ["sitemaps", selectedSource],
    queryFn: () => sitemapsApi.list(selectedSource || undefined),
    enabled: activeTab === "sitemaps",
  })

  // 获取待爬文章统计
  const { data: pendingStats, refetch: refetchPendingStats } = useQuery({
    queryKey: ["pending-stats", selectedSource],
    queryFn: () => sitemapsApi.getPendingStats(selectedSource || undefined),
    enabled: activeTab === "pending",
  })

  // 获取待爬文章列表
  const { data: pendingArticles, isLoading: pendingLoading, refetch: refetchPending } = useQuery({
    queryKey: ["pending-articles", selectedSource, pendingPage],
    queryFn: () => sitemapsApi.listPending(
      selectedSource || undefined,
      undefined,
      undefined,
      pendingPageSize,
      (pendingPage - 1) * pendingPageSize
    ),
    enabled: activeTab === "pending",
  })

  // 添加 Sitemap
  const addSitemapMutation = useMutation({
    mutationFn: () => sitemapsApi.addCustom(newSitemapUrl, newSitemapSourceId || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sitemaps"] })
      setAddSitemapOpen(false)
      setNewSitemapUrl("")
      setNewSitemapSourceId(null)
    },
  })

  // 删除 Sitemap
  const deleteSitemapMutation = useMutation({
    mutationFn: (sitemapId: number) => sitemapsApi.delete(sitemapId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sitemaps"] })
    },
  })

  // 从 robots.txt 获取 Sitemap
  const fetchRobotsMutation = useMutation({
    mutationFn: (sourceId: number) => sitemapsApi.fetchRobots(sourceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sitemaps"] })
    },
  })

  // 同步源 Sitemap
  const syncSourceMutation = useMutation({
    mutationFn: (sourceId: number) => sitemapsApi.syncSource(sourceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sitemaps"] })
      queryClient.invalidateQueries({ queryKey: ["pending-stats"] })
      queryClient.invalidateQueries({ queryKey: ["pending-articles"] })
    },
  })

  // 导入文章
  const importArticlesMutation = useMutation({
    mutationFn: (sitemapId: number) => sitemapsApi.importArticles(sitemapId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pending-stats"] })
      queryClient.invalidateQueries({ queryKey: ["pending-articles"] })
    },
  })

  // 删除待爬文章
  const deletePendingMutation = useMutation({
    mutationFn: (articleId: number) => sitemapsApi.deletePending(articleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pending-stats"] })
      queryClient.invalidateQueries({ queryKey: ["pending-articles"] })
    },
  })

  // 爬取单个待爬文章
  const crawlSingleMutation = useMutation({
    mutationFn: (articleId: number) => sitemapsApi.crawlSinglePending(articleId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["pending-stats"] })
      queryClient.invalidateQueries({ queryKey: ["pending-articles"] })
      queryClient.invalidateQueries({ queryKey: ["articles"] })
      alert(data.message || "爬取成功！")
    },
    onError: (error: Error) => {
      alert(`爬取失败: ${error.message}`)
    },
  })

  // 批量爬取待爬文章
  const [batchCrawlLimit, setBatchCrawlLimit] = useState(10)
  const crawlPendingMutation = useMutation({
    mutationFn: ({ sourceId, limit }: { sourceId: number; limit: number }) =>
      sitemapsApi.crawlPending(sourceId, limit),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["pending-stats"] })
      queryClient.invalidateQueries({ queryKey: ["pending-articles"] })
      queryClient.invalidateQueries({ queryKey: ["articles"] })
      alert(data.message || `爬取完成！成功: ${data.crawled}, 失败: ${data.failed}, 跳过: ${data.skipped}`)
    },
    onError: (error: Error) => {
      alert(`批量爬取失败: ${error.message}`)
    },
  })

  // 全局批量爬取 - 使用任务系统 SSE
  const [crawlAllProgress, setCrawlAllProgress] = useState<{
    isRunning: boolean
    currentSource: string
    crawled: number
    failed: number
    skipped: number
    totalSources: number
    currentSourceIndex: number
    taskId: number | null
  }>({
    isRunning: false,
    currentSource: "",
    crawled: 0,
    failed: 0,
    skipped: 0,
    totalSources: 0,
    currentSourceIndex: 0,
    taskId: null,
  })

  const startCrawlAll = (limitPerSource: number) => {
    setCrawlAllProgress({
      isRunning: true,
      currentSource: "准备中...",
      crawled: 0,
      failed: 0,
      skipped: 0,
      totalSources: 0,
      currentSourceIndex: 0,
      taskId: null,
    })

    tasksApi.streamCrawlPending(
      limitPerSource,
      (event) => {
        try {
          const data = JSON.parse(event.data)
          switch (event.type) {
            case "created":
              setCrawlAllProgress(prev => ({
                ...prev,
                taskId: data.task_id,
                currentSource: "任务已创建...",
              }))
              break
            case "status":
              const task = data as Task
              setCrawlAllProgress(prev => ({
                ...prev,
                currentSource: task.error_message || task.status,
                crawled: (task.result as any)?.success || prev.crawled,
                failed: (task.result as any)?.failed || prev.failed,
                skipped: (task.result as any)?.skipped || prev.skipped,
              }))
              // 定期刷新数据
              queryClient.invalidateQueries({ queryKey: ["pending-stats"] })
              queryClient.invalidateQueries({ queryKey: ["pending-articles"] })
              break
            case "event":
              // 任务事件
              if ((data.event_type === "info" || data.event_type === "progress") && data.event_data?.message) {
                setCrawlAllProgress(prev => ({
                  ...prev,
                  currentSource: data.event_data.message,
                  crawled: data.event_data.result?.success ?? prev.crawled,
                  failed: data.event_data.result?.failed ?? prev.failed,
                  skipped: data.event_data.result?.skipped ?? prev.skipped,
                }))
              }
              break
            case "complete":
              const completedTask = data as Task
              const result = completedTask.result as any
              setCrawlAllProgress(prev => ({
                ...prev,
                isRunning: false,
                currentSource: "完成！",
                crawled: result?.success || prev.crawled,
                failed: result?.failed || prev.failed,
                skipped: result?.skipped || prev.skipped,
              }))
              alert(`全局批量爬取完成！\n成功: ${result?.success || 0}, 失败: ${result?.failed || 0}, 跳过: ${result?.skipped || 0}`)
              // 刷新数据
              queryClient.invalidateQueries({ queryKey: ["pending-stats"] })
              queryClient.invalidateQueries({ queryKey: ["pending-articles"] })
              queryClient.invalidateQueries({ queryKey: ["articles"] })
              break
            case "error":
              setCrawlAllProgress(prev => ({
                ...prev,
                isRunning: false,
                currentSource: "错误",
              }))
              break
          }
        } catch (e) {
          console.error("Failed to parse SSE data:", e)
        }
      },
      () => {
        // onComplete - connection closed
        setCrawlAllProgress(prev => ({ ...prev, isRunning: false }))
        queryClient.invalidateQueries({ queryKey: ["pending-stats"] })
        queryClient.invalidateQueries({ queryKey: ["pending-articles"] })
        queryClient.invalidateQueries({ queryKey: ["articles"] })
      },
      (error) => {
        // onError
        setCrawlAllProgress(prev => ({ ...prev, isRunning: false, currentSource: "错误" }))
        alert(`批量爬取失败: ${error.message}`)
      }
    )
  }

  // 批量重试失败文章 - 使用任务系统 SSE
  const [retryProgress, setRetryProgress] = useState<{
    isRunning: boolean
    currentSource: string
    retried: number
    failed: number
    totalSources: number
    currentSourceIndex: number
    taskId: number | null
  }>({
    isRunning: false,
    currentSource: "",
    retried: 0,
    failed: 0,
    totalSources: 0,
    currentSourceIndex: 0,
    taskId: null,
  })

  const startRetryFailed = (sourceId: number | undefined, limit: number) => {
    setRetryProgress({
      isRunning: true,
      currentSource: "准备中...",
      retried: 0,
      failed: 0,
      totalSources: 0,
      currentSourceIndex: 0,
      taskId: null,
    })

    tasksApi.streamRetryFailed(
      limit,
      (event) => {
        try {
          const data = JSON.parse(event.data)
          switch (event.type) {
            case "created":
              setRetryProgress(prev => ({
                ...prev,
                taskId: data.task_id,
                currentSource: "任务已创建...",
              }))
              break
            case "status":
              const task = data as Task
              setRetryProgress(prev => ({
                ...prev,
                currentSource: task.error_message || task.status,
                retried: (task.result as any)?.success || prev.retried,
                failed: (task.result as any)?.failed || prev.failed,
              }))
              // 定期刷新数据
              queryClient.invalidateQueries({ queryKey: ["pending-stats"] })
              queryClient.invalidateQueries({ queryKey: ["pending-articles"] })
              break
            case "event":
              // 任务事件
              if ((data.event_type === "info" || data.event_type === "progress") && data.event_data?.message) {
                setRetryProgress(prev => ({
                  ...prev,
                  currentSource: data.event_data.message,
                  retried: data.event_data.result?.success ?? prev.retried,
                  failed: data.event_data.result?.failed ?? prev.failed,
                }))
              }
              break
            case "complete":
              const completedTask = data as Task
              const result = completedTask.result as any
              setRetryProgress(prev => ({
                ...prev,
                isRunning: false,
                currentSource: "完成！",
                retried: result?.success || prev.retried,
                failed: result?.failed || prev.failed,
              }))
              alert(`批量重试完成！\n成功: ${result?.success || 0}, 失败: ${result?.failed || 0}`)
              // 刷新数据
              queryClient.invalidateQueries({ queryKey: ["pending-stats"] })
              queryClient.invalidateQueries({ queryKey: ["pending-articles"] })
              queryClient.invalidateQueries({ queryKey: ["articles"] })
              break
            case "error":
              setRetryProgress(prev => ({
                ...prev,
                isRunning: false,
                currentSource: "错误",
              }))
              break
          }
        } catch (e) {
          console.error("Failed to parse SSE data:", e)
        }
      },
      () => {
        // onComplete
        setRetryProgress(prev => ({ ...prev, isRunning: false }))
        queryClient.invalidateQueries({ queryKey: ["pending-stats"] })
        queryClient.invalidateQueries({ queryKey: ["pending-articles"] })
        queryClient.invalidateQueries({ queryKey: ["articles"] })
      },
      (error) => {
        // onError
        setRetryProgress(prev => ({ ...prev, isRunning: false, currentSource: "错误" }))
        alert(`批量重试失败: ${error.message}`)
      }
    )
  }

  // 组件卸载时重置进度状态（防止切换页面后按钮状态不恢复）
  useEffect(() => {
    return () => {
      if (crawlAllProgress.isRunning) {
        setCrawlAllProgress({
          isRunning: false,
          currentSource: "",
          crawled: 0,
          failed: 0,
          skipped: 0,
          totalSources: 0,
          currentSourceIndex: 0,
          taskId: null,
        })
      }
      if (retryProgress.isRunning) {
        setRetryProgress({
          isRunning: false,
          currentSource: "",
          retried: 0,
          failed: 0,
          totalSources: 0,
          currentSourceIndex: 0,
          taskId: null,
        })
      }
    }
  }, []) // 空依赖数组，只在组件卸载时执行

  const sources = sourcesData?.items || []

  // 过滤 Sitemap
  const filteredSitemaps = (sitemaps || []).filter((sitemap) =>
    sitemap.url.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // 获取状态图标
  const getStatusIcon = (status: string) => {
    switch (status) {
      case "success":
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case "failed":
        return <XCircle className="h-4 w-4 text-red-500" />
      case "pending":
        return <Clock className="h-4 w-4 text-yellow-500" />
      default:
        return <AlertCircle className="h-4 w-4 text-gray-500" />
    }
  }

  // 获取待爬状态图标
  const getPendingStatusIcon = (status: string) => {
    switch (status) {
      case "pending":
        return <Clock className="h-4 w-4 text-yellow-500" />
      case "crawling":
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
      case "completed":
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case "failed":
        return <XCircle className="h-4 w-4 text-red-500" />
      case "abandoned":
        return <AlertCircle className="h-4 w-4 text-gray-400" />
      default:
        return <AlertCircle className="h-4 w-4 text-gray-500" />
    }
  }

  return (
    <div className="space-y-6">
      {/* 页面标题和操作 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Sitemap 管理</h1>
          <p className="text-sm text-muted-foreground">管理 Sitemap 和待爬文章队列</p>
        </div>
        <Button onClick={() => setAddSitemapOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          添加 Sitemap
        </Button>
      </div>

      {/* 源选择 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">筛选源</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <Label>选择源:</Label>
            <select
              className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={selectedSource || ""}
              onChange={(e) => setSelectedSource(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">全部源</option>
              {sources.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.site_name} ({source.base_url})
                </option>
              ))}
            </select>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                refetchSitemaps()
                refetchPendingStats()
                refetchPending()
              }}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              刷新
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Tab 切换 */}
      <div className="flex gap-2 border-b">
        <button
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === "sitemaps"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setActiveTab("sitemaps")}
        >
          <Globe className="mr-2 h-4 w-4 inline" />
          Sitemap 列表
        </button>
        <button
          className={`px-4 py-2 font-medium transition-colors ${
            activeTab === "pending"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => setActiveTab("pending")}
        >
          <FileText className="mr-2 h-4 w-4 inline" />
          待爬文章
          {pendingStats && pendingStats.pending > 0 && (
            <span className="ml-2 rounded-full bg-primary px-2 py-0.5 text-xs text-primary-foreground">
              {pendingStats.pending}
            </span>
          )}
        </button>
      </div>

      {/* Sitemap 列表 */}
      {activeTab === "sitemaps" && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">Sitemap 列表</CardTitle>
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="搜索 Sitemap URL..."
                    className="pl-8 w-64"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {sitemapsLoading ? (
              <div className="flex h-32 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : filteredSitemaps.length === 0 ? (
              <div className="flex h-32 items-center justify-center text-muted-foreground">
                {searchQuery ? "未找到匹配的 Sitemap" : "暂无 Sitemap，请添加或从 robots.txt 获取"}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16">状态</TableHead>
                    <TableHead>URL</TableHead>
                    <TableHead className="w-24">源 ID</TableHead>
                    <TableHead className="w-32">最后抓取</TableHead>
                    <TableHead className="w-24">文章数</TableHead>
                    <TableHead className="w-32">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredSitemaps.map((sitemap) => (
                    <TableRow key={sitemap.id}>
                      <TableCell>{getStatusIcon(sitemap.fetch_status)}</TableCell>
                      <TableCell className="max-w-md truncate font-mono text-xs">
                        {sitemap.url}
                      </TableCell>
                      <TableCell>{sitemap.source_id}</TableCell>
                      <TableCell className="text-sm">
                        {formatDateTime(sitemap.last_fetched)}
                      </TableCell>
                      <TableCell>{sitemap.article_count}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => importArticlesMutation.mutate(sitemap.id)}
                            disabled={importArticlesMutation.isPending}
                            title="导入文章到待爬表"
                          >
                            <Download className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => {
                              if (confirm("确定要删除这个 Sitemap 吗？")) {
                                deleteSitemapMutation.mutate(sitemap.id)
                              }
                            }}
                            disabled={deleteSitemapMutation.isPending}
                            title="删除"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {/* 待爬文章列表 */}
      {activeTab === "pending" && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">待爬文章</CardTitle>
              {pendingStats && (
                <div className="flex items-center gap-4 text-sm">
                  <span>总计: {pendingStats.total}</span>
                  <span className="text-yellow-600">待爬: {pendingStats.pending}</span>
                  <span className="text-green-600">已完成: {pendingStats.completed}</span>
                  <span className="text-red-600">失败: {pendingStats.failed}</span>
                  <span className="text-gray-500">遗弃: {pendingStats.abandoned || 0}</span>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {pendingLoading ? (
              <div className="flex h-32 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : !pendingArticles || pendingArticles.length === 0 ? (
              <div className="flex h-32 items-center justify-center text-muted-foreground">
                暂无待爬文章
              </div>
            ) : (
              <div className="space-y-4">
                {/* 批量操作区域 */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-4 bg-muted rounded-lg">
                    <div className="flex items-center gap-4">
                      {selectedSource ? (
                        <div className="text-sm">
                          <span className="font-medium">当前选中源:</span> {sources.find(s => s.id === selectedSource)?.site_name}
                        </div>
                      ) : (
                        <div className="text-sm">
                          <span className="font-medium">全局批量操作</span>
                          <span className="text-muted-foreground ml-2">（将处理所有源的文章）</span>
                        </div>
                      )}
                      <div className="flex items-center gap-2">
                        <Label htmlFor="batch-limit" className="text-sm">每个源数量:</Label>
                        <Input
                          id="batch-limit"
                          type="number"
                          min={1}
                          max={100}
                          value={batchCrawlLimit}
                          onChange={(e) => setBatchCrawlLimit(Math.min(100, Math.max(1, Number(e.target.value) || 1)))}
                          className="w-20 h-8"
                          disabled={crawlAllProgress.isRunning || retryProgress.isRunning}
                        />
                        <span className="text-xs text-muted-foreground">待爬: {pendingStats?.pending || 0} | 失败: {pendingStats?.failed || 0} | 遗弃: {pendingStats?.abandoned || 0}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {/* 批量爬取按钮 */}
                      <Button
                        size="sm"
                        variant="default"
                        onClick={() => {
                          if (selectedSource) {
                            crawlPendingMutation.mutate({ sourceId: selectedSource, limit: batchCrawlLimit })
                          } else {
                            startCrawlAll(batchCrawlLimit)
                          }
                        }}
                        disabled={(crawlPendingMutation.isPending || crawlAllProgress.isRunning || retryProgress.isRunning) || !pendingStats || pendingStats.pending === 0}
                      >
                        {(crawlPendingMutation.isPending || crawlAllProgress.isRunning) ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <Download className="mr-2 h-4 w-4" />
                        )}
                        {selectedSource ? `爬取 (${batchCrawlLimit})` : `全局爬取`}
                      </Button>
                      {/* 批量重试按钮 */}
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => startRetryFailed(selectedSource || undefined, batchCrawlLimit)}
                        disabled={(crawlPendingMutation.isPending || crawlAllProgress.isRunning || retryProgress.isRunning) || !pendingStats || pendingStats.failed === 0}
                      >
                        {retryProgress.isRunning ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <RefreshCw className="mr-2 h-4 w-4" />
                        )}
                        重试失败 ({pendingStats?.failed || 0})
                      </Button>
                    </div>
                  </div>

                  {/* 实时进度显示 */}
                  {(crawlAllProgress.isRunning || retryProgress.isRunning) && (
                    <div className="p-3 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-lg">
                      <div className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                          <span className="font-medium">
                            {crawlAllProgress.isRunning ? "批量爬取中" : "批量重试中"}
                          </span>
                          <span className="text-muted-foreground">|</span>
                          <span>{crawlAllProgress.isRunning ? crawlAllProgress.currentSource : retryProgress.currentSource}</span>
                        </div>
                        <div className="flex items-center gap-4 text-xs">
                          {crawlAllProgress.isRunning ? (
                            <>
                              <span className="text-green-600">成功: {crawlAllProgress.crawled}</span>
                              <span className="text-red-600">失败: {crawlAllProgress.failed}</span>
                              <span className="text-gray-600">跳过: {crawlAllProgress.skipped}</span>
                              <span className="text-muted-foreground">
                                源: {crawlAllProgress.currentSourceIndex}/{crawlAllProgress.totalSources}
                              </span>
                            </>
                          ) : (
                            <>
                              <span className="text-green-600">成功: {retryProgress.retried}</span>
                              <span className="text-red-600">失败: {retryProgress.failed}</span>
                              <span className="text-muted-foreground">
                                源: {retryProgress.currentSourceIndex}/{retryProgress.totalSources}
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-16">状态</TableHead>
                      <TableHead>标题</TableHead>
                      <TableHead className="w-24">源 ID</TableHead>
                      <TableHead className="w-32">发布时间</TableHead>
                      <TableHead className="w-32">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pendingArticles.map((article) => (
                      <TableRow key={article.id}>
                        <TableCell>{getPendingStatusIcon(article.status)}</TableCell>
                        <TableCell>
                          <div className="max-w-md">
                            <div className="truncate text-sm font-medium">
                              {article.title || "无标题"}
                            </div>
                            <div className="truncate text-xs text-muted-foreground font-mono">
                              {article.url}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>{article.source_id}</TableCell>
                        <TableCell className="text-sm">
                          {formatDateTime(article.publish_time)}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            {/* 单个爬取按钮 - 只在待爬状态显示 */}
                            {article.status === "pending" && (
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={() => crawlSingleMutation.mutate(article.id)}
                                disabled={crawlSingleMutation.isPending}
                                title="爬取这篇文章"
                              >
                                {crawlSingleMutation.isPending ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <Download className="h-4 w-4" />
                                )}
                              </Button>
                            )}
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => {
                                if (confirm("确定要删除这篇待爬文章吗？")) {
                                  deletePendingMutation.mutate(article.id)
                                }
                              }}
                              disabled={deletePendingMutation.isPending}
                              title="删除"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                {/* 分页 */}
                {pendingStats && pendingStats.total > 0 && (
                  <div className="flex items-center justify-between mt-4 pt-4 border-t">
                    <div className="text-sm text-muted-foreground">
                      显示第 {(pendingPage - 1) * pendingPageSize + 1} - {Math.min(pendingPage * pendingPageSize, pendingStats.total)} 条，
                      共 {pendingStats.total} 条
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPendingPage(p => Math.max(1, p - 1))}
                        disabled={pendingPage === 1 || pendingLoading}
                      >
                        上一页
                      </Button>
                      <span className="text-sm">
                        第 {pendingPage} / {Math.ceil(pendingStats.total / pendingPageSize)} 页
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPendingPage(p => p + 1)}
                        disabled={pendingPage >= Math.ceil(pendingStats.total / pendingPageSize) || pendingLoading}
                      >
                        下一页
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* 源快速操作 */}
      {selectedSource && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">源操作 - {sources.find(s => s.id === selectedSource)?.site_name}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={() => fetchRobotsMutation.mutate(selectedSource)}
                disabled={fetchRobotsMutation.isPending}
              >
                {fetchRobotsMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Globe className="mr-2 h-4 w-4" />
                )}
                从 robots.txt 获取 Sitemap
              </Button>
              <Button
                variant="outline"
                onClick={() => syncSourceMutation.mutate(selectedSource)}
                disabled={syncSourceMutation.isPending}
              >
                {syncSourceMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Download className="mr-2 h-4 w-4" />
                )}
                同步 Sitemap 文章
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 添加 Sitemap 对话框 */}
      <Dialog open={addSitemapOpen} onOpenChange={setAddSitemapOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>添加 Sitemap</DialogTitle>
            <DialogDescription>
              输入 Sitemap URL，系统会自动匹配或创建对应的源。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Sitemap URL</Label>
              <Input
                placeholder="https://example.com/sitemap.xml"
                value={newSitemapUrl}
                onChange={(e) => setNewSitemapUrl(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>关联源（可选）</Label>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={newSitemapSourceId || ""}
                onChange={(e) => setNewSitemapSourceId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">自动匹配</option>
                {sources.map((source) => (
                  <option key={source.id} value={source.id}>
                    {source.site_name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddSitemapOpen(false)}>
              取消
            </Button>
            <Button
              onClick={() => addSitemapMutation.mutate()}
              disabled={addSitemapMutation.isPending || !newSitemapUrl.trim()}
            >
              {addSitemapMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              添加
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
