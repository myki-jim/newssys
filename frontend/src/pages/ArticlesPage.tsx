import { useState, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { articlesApi } from "@/services/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Search,
  RefreshCw,
  ExternalLink,
  RotateCcw,
  Trash2,
  CheckCircle,
  XCircle,
  Clock,
  Eye,
  Edit,
  Loader2,
  Eraser,
  ChevronLeft,
  ChevronRight,
  X,
  Calendar,
} from "lucide-react"
import { formatDateTime, truncateText } from "@/lib/utils"
import type { Article } from "@/types"
import { ArticleEditDialog } from "@/components/articles/ArticleEditDialog"

const PAGE_SIZE = 30

export function ArticlesPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  // 搜索和筛选状态
  const [searchQuery, setSearchQuery] = useState("")
  const [sourceSearch, setSourceSearch] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")

  // 日期范围状态
  const [publishTimeStart, setPublishTimeStart] = useState("")
  const [publishTimeEnd, setPublishTimeEnd] = useState("")
  const [crawlTimeStart, setCrawlTimeStart] = useState("")
  const [crawlTimeEnd, setCrawlTimeEnd] = useState("")

  // 计算筛选参数
  const searchKeyword = searchQuery.trim() || undefined
  const sourceSearchKeyword = sourceSearch.trim() || undefined

  // 分页状态
  const [currentPage, setCurrentPage] = useState(1)

  // 选择状态
  const [selectedArticles, setSelectedArticles] = useState<Set<number>>(new Set())
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null)
  const [editOpen, setEditOpen] = useState(false)

  // 构建日期范围对象
  const publishTimeRange = (publishTimeStart || publishTimeEnd)
    ? {
        start: publishTimeStart || undefined,
        end: publishTimeEnd || undefined,
      }
    : undefined

  const crawlTimeRange = (crawlTimeStart || crawlTimeEnd)
    ? {
        start: crawlTimeStart || undefined,
        end: crawlTimeEnd || undefined,
      }
    : undefined

  // 获取文章列表
  const { data: articlesData, isLoading, refetch } = useQuery({
    queryKey: ["articles", currentPage, statusFilter, searchKeyword, sourceSearchKeyword, publishTimeRange, crawlTimeRange],
    queryFn: () =>
      articlesApi.list({
        page: currentPage,
        page_size: PAGE_SIZE,
        sort_by: "created_at",
        sort_order: "desc",
        ...(statusFilter !== "all" && { status: statusFilter }),
        ...(searchKeyword && { keyword: searchKeyword }),
        ...(sourceSearchKeyword && { source_search: sourceSearchKeyword }),
        ...(publishTimeRange && { publish_time_range: publishTimeRange }),
        ...(crawlTimeRange && { date_range: crawlTimeRange }),
      }),
    enabled: true,
  })

  const articles = articlesData?.items || []
  const totalCount = articlesData?.total || 0
  const totalPages = Math.ceil(totalCount / PAGE_SIZE)

  // 搜索时重置到第一页
  useEffect(() => {
    setCurrentPage(1)
  }, [searchKeyword, sourceSearchKeyword, statusFilter, publishTimeRange, crawlTimeRange])

  // 批量重试
  const bulkRetryMutation = useMutation({
    mutationFn: () => articlesApi.bulkRetry(),
    onSuccess: () => {
      refetch()
      setSelectedArticles(new Set())
    },
  })

  // 批量删除
  const bulkDeleteMutation = useMutation({
    mutationFn: (ids: number[]) => articlesApi.bulkDelete(ids),
    onSuccess: () => {
      refetch()
      setSelectedArticles(new Set())
    },
  })

  // 标记低质量文章和待爬文章
  const cleanupMutation = useMutation({
    mutationFn: () => articlesApi.cleanup(),
    onSuccess: (data) => {
      refetch()
      alert(`标记完成！成功标记 ${data.success_count} 条记录为低质量${data.failed_count > 0 ? `，失败 ${data.failed_count} 条` : ''}`)
    },
  })

  // 单个重新爬取
  const refetchMutation = useMutation({
    mutationFn: (articleId: number) => articlesApi.refetch(articleId),
    onSuccess: () => {
      refetch()
    },
  })

  // 清空所有筛选
  const clearAllFilters = () => {
    setSearchQuery("")
    setSourceSearch("")
    setStatusFilter("all")
    setPublishTimeStart("")
    setPublishTimeEnd("")
    setCrawlTimeStart("")
    setCrawlTimeEnd("")
  }

  // 获取状态图标
  const getStatusBadge = (article: Article) => {
    const isFailed = article.status === "failed" || article.fetch_status === "failed"
    const isPending = article.fetch_status === "pending" || article.fetch_status === "retry"

    if (isFailed) {
      return (
        <span className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs bg-destructive/10 text-destructive">
          <XCircle className="h-3 w-3" />
          失败
        </span>
      )
    }

    if (isPending) {
      return (
        <span className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300">
          <Clock className="h-3 w-3" />
          待处理
        </span>
      )
    }

    return (
      <span className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
        <CheckCircle className="h-3 w-3" />
        成功
      </span>
    )
  }

  const handleSelectAll = () => {
    if (selectedArticles.size === articles.length) {
      setSelectedArticles(new Set())
    } else {
      setSelectedArticles(new Set(articles.map((a) => a.id)))
    }
  }

  const handleSelectArticle = (id: number) => {
    const newSelected = new Set(selectedArticles)
    if (newSelected.has(id)) {
      newSelected.delete(id)
    } else {
      newSelected.add(id)
    }
    setSelectedArticles(newSelected)
  }

  const handleViewArticle = (articleId: number) => {
    navigate(`/articles/${articleId}`)
  }

  const handleSearch = () => {
    setCurrentPage(1)
    refetch()
  }

  const hasActiveFilters = searchQuery || sourceSearch || statusFilter !== "all" ||
    publishTimeStart || publishTimeEnd || crawlTimeStart || crawlTimeEnd

  return (
    <div className="space-y-6">
      {/* 页面标题和操作 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">文章管理库</h1>
          <p className="text-muted-foreground">
            管理采集的文章，支持搜索、筛选和批量操作
          </p>
        </div>
        <div className="flex items-center gap-2">
          {hasActiveFilters && (
            <Button variant="outline" onClick={clearAllFilters}>
              <X className="mr-2 h-4 w-4" />
              清空筛选
            </Button>
          )}
          <Button
            variant="outline"
            onClick={() => {
              if (confirm("确定要标记低质量内容吗？\n\n文章标记条件：\n• 内容少于 50 字符\n• 没有发布时间\n• 发布时间在一年之外\n\n待爬文章标记条件：\n• 没有发布时间\n• 发布时间在一年之外\n\n标记后的内容将被隐藏，不会参与任何操作。")) {
                cleanupMutation.mutate()
              }
            }}
            disabled={cleanupMutation.isPending}
          >
            {cleanupMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Eraser className="mr-2 h-4 w-4" />
            )}
            清理低质量内容
          </Button>
        </div>
      </div>

      {/* 搜索和筛选 */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-4">
            {/* 第一行：搜索框 */}
            <div className="flex items-center gap-4">
              {/* 文章搜索 */}
              <div className="flex items-center gap-2 flex-1">
                <Search className="h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="搜索标题、内容或 URL..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      handleSearch()
                    }
                  }}
                  className="flex-1"
                />
              </div>

              {/* 源搜索 */}
              <div className="flex items-center gap-2 w-64">
                <Search className="h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="搜索源名称..."
                  value={sourceSearch}
                  onChange={(e) => setSourceSearch(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      handleSearch()
                    }
                  }}
                  className="flex-1"
                />
              </div>

              {/* 状态筛选 */}
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">状态:</span>
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-[150px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部状态</SelectItem>
                    <SelectItem value="raw">原始</SelectItem>
                    <SelectItem value="processed">已处理</SelectItem>
                    <SelectItem value="synced">已同步</SelectItem>
                    <SelectItem value="failed">失败</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* 第二行：日期范围 */}
            <div className="flex items-center gap-4">
              {/* 发布时间范围 */}
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">发布时间:</span>
                <Input
                  type="date"
                  value={publishTimeStart}
                  onChange={(e) => setPublishTimeStart(e.target.value)}
                  className="w-36"
                />
                <span className="text-sm text-muted-foreground">至</span>
                <Input
                  type="date"
                  value={publishTimeEnd}
                  onChange={(e) => setPublishTimeEnd(e.target.value)}
                  className="w-36"
                />
              </div>

              {/* 采集时间范围 */}
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">采集时间:</span>
                <Input
                  type="date"
                  value={crawlTimeStart}
                  onChange={(e) => setCrawlTimeStart(e.target.value)}
                  className="w-36"
                />
                <span className="text-sm text-muted-foreground">至</span>
                <Input
                  type="date"
                  value={crawlTimeEnd}
                  onChange={(e) => setCrawlTimeEnd(e.target.value)}
                  className="w-36"
                />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 批量操作 */}
      {selectedArticles.size > 0 && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                已选 {selectedArticles.size} 项
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => bulkRetryMutation.mutate()}
                  disabled={bulkRetryMutation.isPending}
                >
                  <RotateCcw className="mr-2 h-4 w-4" />
                  重试
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => bulkDeleteMutation.mutate(Array.from(selectedArticles))}
                  disabled={bulkDeleteMutation.isPending}
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  删除
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 文章列表 */}
      <Card>
        <CardHeader>
          <CardTitle>文章列表 ({totalCount})</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : articles.length > 0 ? (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">
                        <input
                          type="checkbox"
                          checked={selectedArticles.size === articles.length && articles.length > 0}
                          onChange={handleSelectAll}
                          className="h-4 w-4"
                        />
                      </TableHead>
                      <TableHead>标题</TableHead>
                      <TableHead>来源</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead>发布时间</TableHead>
                      <TableHead>采集时间</TableHead>
                      <TableHead className="text-right">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {articles.map((article) => (
                      <TableRow key={article.id}>
                        <TableCell>
                          <input
                            type="checkbox"
                            checked={selectedArticles.has(article.id)}
                            onChange={() => handleSelectArticle(article.id)}
                            className="h-4 w-4"
                          />
                        </TableCell>
                        <TableCell>
                          <div className="max-w-md">
                            <div className="font-medium">{truncateText(article.title, 80)}</div>
                            <div className="text-xs text-muted-foreground">{article.url}</div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className="text-sm text-muted-foreground">源 #{article.source_id}</span>
                        </TableCell>
                        <TableCell>{getStatusBadge(article)}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {formatDateTime(article.publish_time)}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {formatDateTime(article.created_at)}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleViewArticle(article.id)}
                              title="查看详情"
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => {
                                if (confirm(`确定要重新爬取这篇文章吗？\n${article.title}`)) {
                                  refetchMutation.mutate(article.id)
                                }
                              }}
                              title="重新爬取"
                              disabled={refetchMutation.isPending}
                            >
                              <RefreshCw className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => {
                                setSelectedArticle(article)
                                setEditOpen(true)
                              }}
                              title="编辑"
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" asChild title="原始链接">
                              <a href={article.url} target="_blank" rel="noopener noreferrer">
                                <ExternalLink className="h-4 w-4" />
                              </a>
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* 分页控件 */}
              <div className="flex items-center justify-between mt-4 pt-4 border-t">
                <div className="text-sm text-muted-foreground">
                  显示 {(currentPage - 1) * PAGE_SIZE + 1} - {Math.min(currentPage * PAGE_SIZE, totalCount)} 条，共 {totalCount} 条
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(1)}
                    disabled={currentPage === 1}
                  >
                    首页
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                    上一页
                  </Button>
                  <span className="text-sm">
                    第 <span className="font-medium">{currentPage}</span> / {totalPages} 页
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    disabled={currentPage === totalPages || totalPages === 0}
                  >
                    下一页
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(totalPages)}
                    disabled={currentPage === totalPages || totalPages === 0}
                  >
                    末页
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <div className="flex h-64 flex-col items-center justify-center text-muted-foreground">
              <Search className="h-12 w-12 mb-4 opacity-50" />
              <p>暂无文章</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 文章编辑对话框 */}
      <ArticleEditDialog
        article={selectedArticle}
        open={editOpen}
        onOpenChange={setEditOpen}
      />
    </div>
  )
}
