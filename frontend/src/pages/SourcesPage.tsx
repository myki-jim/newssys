import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { sourcesApi } from "@/services/api"
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
  Plus,
  Search,
  RefreshCw,
  Settings,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
} from "lucide-react"
import { formatDateTime } from "@/lib/utils"
import { cn } from "@/lib/utils"
import { SourceBulkImportDialog } from "@/components/sources/SourceBulkImportDialog"
import { SourceDebugDrawer } from "@/components/sources/SourceDebugDrawer"
import { SourceSitemapDialog } from "@/components/sources/SourceSitemapDialog"

export function SourcesPage() {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState("")
  const [page, setPage] = useState(1)
  const [selectedSource, setSelectedSource] = useState<number | null>(null)
  const [bulkImportOpen, setBulkImportOpen] = useState(false)
  const [debugDrawerOpen, setDebugDrawerOpen] = useState(false)
  const [sitemapDialogOpen, setSitemapDialogOpen] = useState(false)

  // 获取源列表
  const { data: sourcesData, isLoading } = useQuery({
    queryKey: ["sources", page],
    queryFn: () => sourcesApi.list({ page, page_size: 20 }),
  })

  // 抓取 Sitemap
  const fetchSitemapMutation = useMutation({
    mutationFn: (sourceId: number) => sourcesApi.fetchSitemap(sourceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] })
    },
  })

  // 抓取 Robots
  const fetchRobotsMutation = useMutation({
    mutationFn: (sourceId: number) => sourcesApi.fetchRobots(sourceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] })
    },
  })

  // 触发抓取
  const triggerCrawlMutation = useMutation({
    mutationFn: ({ sourceId, force }: { sourceId: number; force: boolean }) =>
      sourcesApi.triggerCrawl(sourceId, force),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sources"] })
    },
  })

  const sources = sourcesData?.items || []
  const totalPages = sourcesData?.total_pages || 0

  // 过滤
  const filteredSources = sources.filter((source) =>
    source.site_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    source.base_url.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // 获取状态图标
  const getStatusIcon = (status: string) => {
    switch (status) {
      case "compliant":
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case "restricted":
        return <XCircle className="h-4 w-4 text-red-500" />
      case "error":
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case "pending":
        return <Clock className="h-4 w-4 text-yellow-500" />
      default:
        return <CheckCircle className="h-4 w-4 text-gray-500" />
    }
  }

  return (
    <div className="space-y-6">
      {/* 页面标题和操作 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">采集源管理</h1>
          <p className="text-muted-foreground">
            管理新闻采集源配置，查看 Sitemap 和 Robots 状态
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setBulkImportOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            批量导入
          </Button>
          <Button onClick={() => setBulkImportOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            添加源
          </Button>
        </div>
      </div>

      {/* 搜索栏 */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center gap-2">
            <Search className="h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="搜索站点名称或 URL..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1"
            />
          </div>
        </CardContent>
      </Card>

      {/* 源列表 */}
      <Card>
        <CardHeader>
          <CardTitle>源列表 ({filteredSources.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>站点名称</TableHead>
                    <TableHead>基础 URL</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>Robots</TableHead>
                    <TableHead>文章数</TableHead>
                    <TableHead>成功率</TableHead>
                    <TableHead>最后抓取</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredSources.map((source) => (
                    <TableRow key={source.id}>
                      <TableCell className="font-medium">{source.site_name}</TableCell>
                      <TableCell className="max-w-xs truncate text-muted-foreground">
                        {source.base_url}
                      </TableCell>
                      <TableCell>
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs",
                            source.enabled
                              ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                              : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
                          )}
                        >
                          {source.enabled ? "启用" : "禁用"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          {getStatusIcon(source.robots_status)}
                          <span className="text-xs text-muted-foreground">
                            {source.crawl_delay ? `${source.crawl_delay}s` : "-"}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>{source.success_count + source.failure_count}</TableCell>
                      <TableCell>
                        {source.success_count + source.failure_count > 0 ? (
                          <span
                            className={cn(
                              "font-medium",
                              (source.success_count / (source.success_count + source.failure_count)) * 100 <
                                80
                                ? "text-destructive"
                                : "text-green-600"
                            )}
                          >
                            {Math.round(
                              (source.success_count /
                                (source.success_count + source.failure_count)) *
                                100
                            )}
                            %
                          </span>
                        ) : (
                          "-"
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDateTime(source.last_crawled_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => {
                              setSelectedSource(source.id)
                              setDebugDrawerOpen(true)
                            }}
                            title="调试配置"
                          >
                            <Settings className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => {
                              setSelectedSource(source.id)
                              setSitemapDialogOpen(true)
                            }}
                            title="查看 Sitemap"
                          >
                            <Search className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => fetchSitemapMutation.mutate(source.id)}
                            disabled={fetchSitemapMutation.isPending}
                            title="刷新 Sitemap"
                          >
                            <RefreshCw
                              className={cn(
                                "h-4 w-4",
                                fetchSitemapMutation.isPending && "animate-spin"
                              )}
                            />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => triggerCrawlMutation.mutate({ sourceId: source.id, force: false })}
                            disabled={triggerCrawlMutation.isPending}
                            title="立即抓取"
                          >
                            <RefreshCw
                              className={cn(
                                "h-4 w-4",
                                triggerCrawlMutation.isPending && "animate-spin"
                              )}
                            />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* 分页 */}
              {totalPages > 1 && (
                <div className="flex items-center justify-end gap-2 mt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                  >
                    上一页
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    第 {page} / {totalPages} 页
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                  >
                    下一页
                  </Button>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 对话框和抽屉 */}
      {selectedSource && (
        <>
          <SourceBulkImportDialog
            open={bulkImportOpen}
            onOpenChange={setBulkImportOpen}
          />
          <SourceDebugDrawer
            open={debugDrawerOpen}
            onOpenChange={setDebugDrawerOpen}
            sourceId={selectedSource}
          />
          <SourceSitemapDialog
            open={sitemapDialogOpen}
            onOpenChange={setSitemapDialogOpen}
            sourceId={selectedSource}
          />
        </>
      )}
    </div>
  )
}
