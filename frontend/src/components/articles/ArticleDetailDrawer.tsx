import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { articlesApi } from "@/services/api"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from "@/components/ui/sheet"
import { ExternalLink, Edit, Trash2, Eye, Loader2 } from "lucide-react"
import { formatDateTime } from "@/lib/utils"
import type { Article } from "@/types"

interface ArticleDetailDrawerProps {
  articleId: number | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onEdit: (article: Article) => void
}

export function ArticleDetailDrawer({
  articleId,
  open,
  onOpenChange,
  onEdit,
}: ArticleDetailDrawerProps) {
  const queryClient = useQueryClient()
  const [showBrowser, setShowBrowser] = useState(false)
  const [renderError, setRenderError] = useState<string | null>(null)

  const { data: article, isLoading, error } = useQuery({
    queryKey: ["article", articleId],
    queryFn: () => articlesApi.get(articleId!),
    enabled: !!articleId && open,
    retry: false,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => articlesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["articles"] })
      onOpenChange(false)
    },
  })

  // 捕获渲染错误
  if (error) {
    return (
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent className="w-full sm:max-w-2xl">
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <p className="text-destructive">加载文章失败</p>
              <p className="text-sm text-muted-foreground mt-2">
                {error instanceof Error ? error.message : "未知错误"}
              </p>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    )
  }

  if (!articleId) return null

  if (renderError) {
    return (
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent className="w-full sm:max-w-2xl">
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <p className="text-destructive">渲染错误</p>
              <p className="text-sm text-muted-foreground mt-2">{renderError}</p>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    )
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-2xl overflow-y-auto">
        {isLoading ? (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : article ? (
          <>
            <SheetHeader>
              <SheetTitle>文章详情</SheetTitle>
              <SheetDescription>
                文章 ID: {article?.id ?? "未知"} · 采集于 {formatDateTime(article?.created_at)}
              </SheetDescription>
            </SheetHeader>

            <div className="space-y-6 py-4">
              {/* 标题和操作 */}
              <div className="space-y-4">
                <div>
                  <Label className="text-xs text-muted-foreground">标题</Label>
                  <h2 className="text-lg font-semibold mt-1">{article?.title || "无标题"}</h2>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-xs text-muted-foreground">来源 ID</Label>
                    <p className="text-sm">{article?.source_id ?? "未知"}</p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">作者</Label>
                    <p className="text-sm">{article?.author || "未知"}</p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">发布时间</Label>
                    <p className="text-sm">{formatDateTime(article?.publish_time)}</p>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">状态</Label>
                    <p className="text-sm">{article?.status || "未知"}</p>
                  </div>
                </div>

                <div>
                  <Label className="text-xs text-muted-foreground">文章 URL</Label>
                  <div className="flex items-center gap-2 mt-1">
                    <p className="text-sm text-muted-foreground truncate flex-1">
                      {article?.url || "无"}
                    </p>
                    {article?.url && (
                      <Button
                        variant="outline"
                        size="icon"
                        asChild
                      >
                        <a href={article.url} target="_blank" rel="noopener noreferrer">
                          <Eye className="h-4 w-4" />
                        </a>
                      </Button>
                    )}
                  </div>
                </div>

                {/* 内置浏览器 */}
                {showBrowser && article?.url && (
                  <div className="space-y-2">
                    <Label className="text-xs text-muted-foreground">内置浏览器预览</Label>
                    <div className="border rounded-lg overflow-hidden">
                      <iframe
                        src={article.url}
                        className="w-full h-96"
                        title={article.title || "预览"}
                        sandbox="allow-same-origin allow-scripts allow-forms"
                      />
                    </div>
                  </div>
                )}

                <div>
                  <Label className="text-xs text-muted-foreground">内容预览</Label>
                  <div className="mt-1 p-4 bg-muted rounded-lg max-h-64 overflow-y-auto">
                    <p className="text-sm whitespace-pre-wrap">
                      {article?.content ? (
                        article.content.length > 500
                          ? article.content.substring(0, 500) + "..."
                          : article.content
                      ) : (
                        <span className="text-muted-foreground">暂无内容</span>
                      )}
                    </p>
                  </div>
                </div>

                {/* 元数据 */}
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">采集时间:</span>{" "}
                    {formatDateTime(article?.crawled_at)}
                  </div>
                  <div>
                    <span className="text-muted-foreground">处理时间:</span>{" "}
                    {formatDateTime(article?.processed_at)}
                  </div>
                  <div>
                    <span className="text-muted-foreground">同步时间:</span>{" "}
                    {formatDateTime(article?.synced_at)}
                  </div>
                  <div>
                    <span className="text-muted-foreground">重试次数:</span>{" "}
                    {article?.retry_count ?? 0}
                  </div>
                </div>

                {/* 错误信息 */}
                {article?.error_msg && (
                  <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
                    <Label className="text-xs text-destructive">错误信息</Label>
                    <p className="text-sm text-destructive mt-1">{article.error_msg}</p>
                  </div>
                )}
              </div>
            </div>

            <SheetFooter>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  onClick={() => setShowBrowser(!showBrowser)}
                >
                  <Eye className="mr-2 h-4 w-4" />
                  {showBrowser ? "隐藏浏览器" : "浏览器预览"}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => article?.url && window.open(article.url, "_blank")}
                  disabled={!article?.url}
                >
                  <ExternalLink className="mr-2 h-4 w-4" />
                  原始链接
                </Button>
                <Button
                  variant="outline"
                  onClick={() => article && onEdit(article)}
                  disabled={!article}
                >
                  <Edit className="mr-2 h-4 w-4" />
                  编辑
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => {
                    if (article && confirm("确定要删除这篇文章吗？")) {
                      deleteMutation.mutate(article.id)
                    }
                  }}
                  disabled={deleteMutation.isPending || !article}
                >
                  {deleteMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="mr-2 h-4 w-4" />
                  )}
                  删除
                </Button>
              </div>
            </SheetFooter>
          </>
        ) : (
          <div className="flex h-full items-center justify-center">
            <p className="text-muted-foreground">文章不存在</p>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
