import { useState, useRef, useCallback, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"
import { articlesApi } from "@/services/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
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
  const [statusFilter, setStatusFilter] = useState<string>("all")

  // 分页状态
  const [allArticles, setAllArticles] = useState<Article[]>([])
  const [page, setPage] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const observerTarget = useRef<HTMLDivElement>(null)

  // 选择状态
  const [selectedArticles, setSelectedArticles] = useState<Set<number>>(new Set())
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null)
  const [editOpen, setEditOpen] = useState(false)

  // 获取第一页文章
  const { data: initialArticles, isLoading, refetch } = useQuery({
    queryKey: ["articles", 0, statusFilter],
    queryFn: () =>
      articlesApi.list({
        page: 1,
        page_size: PAGE_SIZE,
        sort_by: "created_at",
        sort_order: "desc",
        ...(statusFilter !== "all" && { status: statusFilter }),
      }),
    enabled: true,
  })

  // 初始化数据
  useEffect(() => {
    if (initialArticles?.items) {
      setAllArticles(initialArticles.items)
      setHasMore(initialArticles.items.length === PAGE_SIZE)
      setPage(0)
    }
  }, [initialArticles])

  // 加载更多
  const loadMore = useCallback(async () => {
    if (isLoadingMore || !hasMore) return

    setIsLoadingMore(true)
    try {
      const nextPage = page + 1
      const moreData = await articlesApi.list({
        page: nextPage + 1,
        page_size: PAGE_SIZE,
        sort_by: "created_at",
        sort_order: "desc",
        ...(statusFilter !== "all" && { status: statusFilter }),
      })

      setAllArticles((prev) => [...prev, ...moreData.items])
      setPage(nextPage)
      setHasMore(moreData.items.length === PAGE_SIZE)
    } catch (error) {
      console.error("加载更多文章失败:", error)
    } finally {
      setIsLoadingMore(false)
    }
  }, [page, hasMore, isLoadingMore, statusFilter])

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

  // 单条采集
  const fetchSingleMutation = useMutation({
    mutationFn: (url: string) => articlesApi.fetchSingle(url),
    onSuccess: () => {
      refetch()
    },
  })

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

  // 清理低质量文章
  const cleanupMutation = useMutation({
    mutationFn: () => articlesApi.cleanup(),
    onSuccess: (data) => {
      refetch()
      alert(`清理完成！成功删除 ${data.success_count} 篇文章${data.failed_count > 0 ? `，失败 ${data.failed_count} 篇` : ''}`)
    },
  })

  // 单个重新爬取
  const refetchMutation = useMutation({
    mutationFn: (articleId: number) => articlesApi.refetch(articleId),
    onSuccess: () => {
      refetch()
    },
  })

  // 筛选状态变化时重新加载
  useEffect(() => {
    refetch()
  }, [statusFilter])

  const articles = allArticles
  const totalCount = initialArticles?.total || 0

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
        <Button
          variant="outline"
          onClick={() => {
            if (confirm("确定要清理低质量文章吗？\n\n清理条件：\n• 内容少于 50 字符\n• 没有发布时间\n• 发布时间在一年之外\n\n此操作不可撤销！")) {
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
          清理低质量文章
        </Button>
      </div>

      {/* 单条采集 */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="输入 URL 立即采集文章..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && searchQuery) {
                  fetchSingleMutation.mutate(searchQuery)
                  setSearchQuery("")
                }
              }}
              className="flex-1"
            />
            <Button
              onClick={() => {
                if (searchQuery) {
                  fetchSingleMutation.mutate(searchQuery)
                  setSearchQuery("")
                }
              }}
              disabled={fetchSingleMutation.isPending || !searchQuery}
            >
              {fetchSingleMutation.isPending ? (
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Search className="mr-2 h-4 w-4" />
              )}
              立即采集
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 筛选和批量操作 */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">状态:</span>
              <div className="flex gap-1">
                {["all", "raw", "processed", "synced", "failed"].map((status) => (
                  <Button
                    key={status}
                    variant={statusFilter === status ? "default" : "outline"}
                    size="sm"
                    onClick={() => setStatusFilter(status)}
                  >
                    {status === "all" ? "全部" : status}
                  </Button>
                ))}
              </div>
            </div>

            {selectedArticles.size > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">
                  已选 {selectedArticles.size} 项
                </span>
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
            )}
          </div>
        </CardContent>
      </Card>

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

              {!hasMore && articles.length > 0 && (
                <div className="py-4 text-center text-sm text-muted-foreground">
                  已加载全部文章 (共 {totalCount} 篇)
                </div>
              )}
            </div>
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
