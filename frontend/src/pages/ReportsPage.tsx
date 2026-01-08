import { useState, useRef, useCallback, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { reportsApi } from "@/services/api"
import { Button } from "@/components/ui/button"
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
  Sparkles,
  FileText,
  Trash2,
  Loader2,
  CheckCircle,
  Clock,
  XCircle,
  Eye,
  RefreshCw,
  Play,
} from "lucide-react"
import { formatDateTime } from "@/lib/utils"
import { ReportGenerateDialog } from "@/components/reports/ReportGenerateDialog"
import type { Report } from "@/types"

const PAGE_SIZE = 20
const AUTO_REFRESH_INTERVAL = 5000 // 5秒自动刷新

export function ReportsPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [generateDialogOpen, setGenerateDialogOpen] = useState(false)
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(true)

  // 分页状态
  const [allReports, setAllReports] = useState<Report[]>([])
  const [page, setPage] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const observerTarget = useRef<HTMLDivElement>(null)

  // 获取第一页报告
  const { data: initialReports, isLoading, refetch } = useQuery({
    queryKey: ["reports", 0],
    queryFn: () => reportsApi.list(PAGE_SIZE, 0),
    refetchInterval: autoRefreshEnabled ? AUTO_REFRESH_INTERVAL : false, // 自动刷新
  })

  // 初始化数据
  useEffect(() => {
    if (initialReports) {
      setAllReports(initialReports)
      setHasMore(initialReports.length === PAGE_SIZE)
      setPage(0)
    }
  }, [initialReports])

  // 检查是否有正在生成的报告
  const hasGeneratingReports = allReports.some(r => r.status === "generating")

  // 根据是否有正在生成的报告启用/禁用自动刷新
  useEffect(() => {
    setAutoRefreshEnabled(hasGeneratingReports)
  }, [hasGeneratingReports])

  // 加载更多
  const loadMore = useCallback(async () => {
    if (isLoadingMore || !hasMore) return

    setIsLoadingMore(true)
    try {
      const nextPage = page + 1
      const moreReports = await reportsApi.list(PAGE_SIZE, nextPage * PAGE_SIZE)

      setAllReports((prev) => [...prev, ...moreReports])
      setPage(nextPage)
      setHasMore(moreReports.length === PAGE_SIZE)
    } catch (error) {
      console.error("加载更多报告失败:", error)
    } finally {
      setIsLoadingMore(false)
    }
  }, [page, hasMore, isLoadingMore])

  // 无限滚动观察器
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !isLoadingMore) {
          loadMore()
        }
      },
      { threshold: 0.1 }
    )

    const currentTarget = observerTarget.current
    if (currentTarget) {
      observer.observe(currentTarget)
    }

    return () => {
      if (currentTarget) {
        observer.unobserve(currentTarget)
      }
    }
  }, [hasMore, isLoadingMore, loadMore])

  // 删除报告
  const deleteMutation = useMutation({
    mutationFn: (reportId: number) => reportsApi.delete(reportId),
    onSuccess: () => {
      // 从本地状态中移除已删除的报告
      setAllReports((prev) => prev.filter((r) => r.id !== reportId))
    },
  })

  // 完成报告合并
  const completeMutation = useMutation({
    mutationFn: (reportId: number) => reportsApi.complete(reportId),
    onSuccess: (data, reportId) => {
      // 更新本地状态中的报告
      setAllReports((prev) =>
        prev.map((r) =>
          r.id === reportId
            ? { ...r, status: "completed" as const, agent_progress: 100, agent_message: "报告已完成" }
            : r
        )
      )
      // 刷新列表获取最新数据
      refetch()
    },
  })

  const getStatusBadge = (status: Report["status"]) => {
    switch (status) {
      case "completed":
        return (
          <span className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
            <CheckCircle className="h-3 w-3" />
            已完成
          </span>
        )
      case "generating":
        return (
          <span className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300">
            <Loader2 className="h-3 w-3 animate-spin" />
            生成中
          </span>
        )
      case "draft":
        return (
          <span className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300">
            <Clock className="h-3 w-3" />
            草稿
          </span>
        )
      case "failed":
        return (
          <span className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300">
            <XCircle className="h-3 w-3" />
            失败
          </span>
        )
      default:
        return null
    }
  }

  const formatTimeRange = (start: string, end: string) => {
    const startDate = new Date(start)
    const endDate = new Date(end)

    const formatDate = (date: Date) => {
      const month = (date.getMonth() + 1).toString().padStart(2, "0")
      const day = date.getDate().toString().padStart(2, "0")
      return `${month}-${day}`
    }

    // 如果是同一年
    if (startDate.getFullYear() === endDate.getFullYear()) {
      // 如果是同一个月
      if (startDate.getMonth() === endDate.getMonth()) {
        return `${startDate.getFullYear()}-${formatDate(startDate)} 至 ${formatDate(endDate)}`
      }
      return `${startDate.getFullYear()}-${formatDate(startDate)} 至 ${formatDate(endDate)}`
    }

    return `${formatDate(startDate)} 至 ${formatDate(endDate)}`
  }

  const handleViewReport = (reportId: number) => {
    navigate(`/reports/${reportId}`)
  }

  return (
    <div className="space-y-6">
      {/* 页面标题和操作 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">报告生成中心</h1>
          <p className="text-muted-foreground">
            AI Agent 智能报告生成 - 自动聚类、事件提取与结构化分析
            {hasGeneratingReports && (
              <span className="ml-2 inline-flex items-center gap-1 text-primary">
                <Loader2 className="h-3 w-3 animate-spin" />
                有 {allReports.filter(r => r.status === "generating").length} 个报告正在生成
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            onClick={() => refetch()}
            title="手动刷新"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={() => setGenerateDialogOpen(true)}>
            <Sparkles className="mr-2 h-4 w-4" />
            生成新报告
          </Button>
        </div>
      </div>

      {/* 报告列表 */}
      <Card>
        <CardHeader>
          <CardTitle>报告历史 ({allReports.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : allReports.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>标题</TableHead>
                    <TableHead>时间范围</TableHead>
                    <TableHead>文章数</TableHead>
                    <TableHead>事件数</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {allReports.map((report) => (
                    <TableRow key={report.id}>
                      <TableCell>
                        <div className="font-medium">{report.title}</div>
                        {report.language && (
                          <div className="text-xs text-muted-foreground">
                            {report.language === "zh" ? "中文" : "哈萨克语"}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className="text-sm text-muted-foreground">
                          {formatTimeRange(report.time_range_start, report.time_range_end)}
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="text-sm">
                          {report.total_articles} 篇
                          {report.clustered_articles > 0 && report.clustered_articles < report.total_articles && (
                            <span className="text-muted-foreground">
                              {" → "}{report.clustered_articles} 篇
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm">{report.event_count} 个</span>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          {getStatusBadge(report.status)}
                          {/* 生成中的报告显示进度 */}
                          {report.status === "generating" && (
                            <div className="mt-1">
                              <div className="flex items-center gap-2">
                                <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden max-w-[120px]">
                                  <div
                                    className="h-full bg-primary transition-all duration-300"
                                    style={{ width: `${report.agent_progress || 0}%` }}
                                  />
                                </div>
                                <span className="text-xs text-muted-foreground">
                                  {report.agent_progress || 0}%
                                </span>
                              </div>
                              <p className="text-xs text-muted-foreground truncate max-w-[200px]" title={report.agent_message}>
                                {report.agent_message}
                              </p>
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDateTime(report.created_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          {report.status === "generating" ? (
                            // 正在生成：显示查看进度和完成合并按钮
                            <>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleViewReport(report.id)}
                                title="查看生成进度"
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                              {report.agent_message?.includes("已完成") && (
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  onClick={() => completeMutation.mutate(report.id)}
                                  disabled={completeMutation.isPending}
                                  title="完成合并"
                                  className="text-green-600 hover:text-green-700"
                                >
                                  <Play className="h-4 w-4" />
                                </Button>
                              )}
                            </>
                          ) : report.status === "completed" ? (
                            // 已完成：显示查看报告按钮
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleViewReport(report.id)}
                              title="查看报告"
                            >
                              <FileText className="h-4 w-4" />
                            </Button>
                          ) : (
                            // 其他状态：禁用查看
                            <Button
                              variant="ghost"
                              size="icon"
                              disabled
                              title={report.status === "draft" ? "草稿" : "无法查看"}
                            >
                              <FileText className="h-4 w-4" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => deleteMutation.mutate(report.id)}
                            disabled={deleteMutation.isPending}
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

              {/* 加载更多指示器 */}
              {hasMore && (
                <div ref={observerTarget} className="py-4 flex justify-center">
                  {isLoadingMore ? (
                    <div className="flex items-center gap-2 text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span className="text-sm">加载更多...</span>
                    </div>
                  ) : (
                    <div className="text-sm text-muted-foreground">
                      向下滚动加载更多
                    </div>
                  )}
                </div>
              )}

              {!hasMore && allReports.length > 0 && (
                <div className="py-4 text-center text-sm text-muted-foreground">
                  已加载全部报告
                </div>
              )}
            </div>
          ) : (
            <div className="flex h-64 flex-col items-center justify-center text-muted-foreground">
              <FileText className="h-12 w-12 mb-4 opacity-50" />
              <p>暂无报告</p>
              <Button
                variant="outline"
                className="mt-4"
                onClick={() => setGenerateDialogOpen(true)}
              >
                生成第一份报告
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 对话框 */}
      <ReportGenerateDialog
        open={generateDialogOpen}
        onOpenChange={setGenerateDialogOpen}
      />
    </div>
  )
}
