import { useState, useEffect } from "react"
import { useQuery, useMutation } from "@tanstack/react-query"
import { useParams, useNavigate } from "react-router-dom"
import { articlesApi } from "@/services/api"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  ArrowLeft,
  Calendar,
  ExternalLink,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  Edit,
  Share2,
  Image as ImageIcon,
  FileText,
  Hash,
  Globe,
} from "lucide-react"
import { formatDateTime } from "@/lib/utils"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeRaw from "rehype-raw"
import rehypeSanitize from "rehype-sanitize"
import { ArticleEditDialog } from "@/components/articles/ArticleEditDialog"
import type { Article } from "@/types"

export function ArticleDetailPage() {
  const { articleId } = useParams<{ articleId: string }>()
  const navigate = useNavigate()
  const [editOpen, setEditOpen] = useState(false)
  const [currentArticle, setCurrentArticle] = useState<Article | null>(null)

  // 获取文章详情
  const { data: article, isLoading, refetch } = useQuery({
    queryKey: ["articles", articleId],
    queryFn: () => articlesApi.get(Number(articleId)),
    enabled: !!articleId,
  })

  // 同步 currentArticle
  useEffect(() => {
    if (article) {
      setCurrentArticle(article)
    }
  }, [article])

  // 重新爬取
  const refetchMutation = useMutation({
    mutationFn: () => articlesApi.refetch(Number(articleId)),
    onSuccess: () => {
      refetch()
    },
  })

  const getStatusBadge = (article: Article) => {
    const isFailed = article.status === "failed" || article.fetch_status === "failed"
    const isPending = article.fetch_status === "pending" || article.fetch_status === "retry"

    if (isFailed) {
      return (
        <Badge variant="destructive" className="gap-1">
          <XCircle className="h-3 w-3" />
          失败
        </Badge>
      )
    }

    if (isPending) {
      return (
        <Badge variant="outline" className="gap-1 bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900 dark:text-yellow-300 dark:border-yellow-800">
          <Clock className="h-3 w-3" />
          待处理
        </Badge>
      )
    }

    return (
      <Badge variant="outline" className="gap-1 bg-green-100 text-green-700 border-green-200 dark:bg-green-900 dark:text-green-300 dark:border-green-800">
        <CheckCircle className="h-3 w-3" />
        成功
      </Badge>
    )
  }

  const handleShare = async () => {
    if (!article) return

    if (navigator.share) {
      try {
        await navigator.share({
          title: article.title,
          text: article.content?.substring(0, 200) || "",
          url: window.location.href,
        })
      } catch (error) {
        console.log("分享失败:", error)
      }
    } else {
      navigator.clipboard.writeText(window.location.href)
      alert("链接已复制到剪贴板")
    }
  }

  return (
    <div className="min-h-screen bg-background">
      {/* 顶部导航栏 */}
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => navigate(-1)}
                className="shrink-0"
              >
                <ArrowLeft className="h-5 w-5" />
              </Button>
              <div className="min-w-0 flex-1">
                <h1 className="text-lg font-bold truncate">文章详情</h1>
                <p className="text-xs text-muted-foreground">
                  {currentArticle ? formatDateTime(currentArticle.publish_time) : ""}
                </p>
              </div>
            </div>
            {currentArticle && (
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refetchMutation.mutate()}
                  disabled={refetchMutation.isPending}
                >
                  <RefreshCw className={`h-4 w-4 mr-2 ${refetchMutation.isPending ? "animate-spin" : ""}`} />
                  重新爬取
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setEditOpen(true)}
                >
                  <Edit className="h-4 w-4 mr-2" />
                  编辑
                </Button>
                <Button variant="outline" size="sm" onClick={handleShare}>
                  <Share2 className="h-4 w-4 mr-2" />
                  分享
                </Button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* 主要内容 */}
      <main className="container mx-auto px-4 py-8 max-w-4xl">
        {isLoading ? (
          <div className="flex h-64 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        ) : article ? (
          <div className="space-y-6">
            {/* 文章元信息 */}
            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <div className="flex items-center gap-2">
                    <Hash className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">源 ID：</span>
                    <span>{article.source_id}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">发布时间：</span>
                    <span>{formatDateTime(article.publish_time)}</span>
                  </div>
                  {getStatusBadge(article)}
                  {article.author && (
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-muted-foreground" />
                      <span className="text-muted-foreground">作者：</span>
                      <span>{article.author}</span>
                    </div>
                  )}
                </div>

                {/* Tags from extra_data */}
                {(() => {
                  const tags = article.extra_data?.tags as string[] | undefined
                  if (!tags || tags.length === 0) return null
                  return (
                    <div className="flex flex-wrap gap-2 mt-4">
                      {tags.map((tag, index) => (
                        <Badge key={index} variant="secondary" className="text-xs">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  )
                })()}
              </CardContent>
            </Card>

            {/* 文章标题 */}
            <div className="space-y-4">
              <h1 className="text-3xl font-bold leading-tight">{article.title ?? "无标题"}</h1>

              {/* 原始链接 */}
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
              >
                <Globe className="h-4 w-4" />
                查看原始链接
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>

            {/* 文章内容 */}
            <Card>
              <CardContent className="pt-6">
                {article.content ? (
                  <div className="prose-markdown dark:prose-invert">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeRaw, rehypeSanitize]}
                      components={{
                        img: ({ node, ...props }) => (
                          <div className="my-6">
                            <img
                              {...props}
                              className="rounded-lg shadow-lg max-h-[600px] w-auto mx-auto"
                              alt={props.alt || "图片"}
                              loading="lazy"
                            />
                            {props.alt && (
                              <p className="text-center text-sm text-muted-foreground mt-2">
                                {props.alt}
                              </p>
                            )}
                          </div>
                        ),
                        h1: ({ node, ...props }) => (
                          <h1 className="text-3xl font-bold mt-8 mb-4 first:mt-0" {...props} />
                        ),
                        h2: ({ node, ...props }) => (
                          <h2 className="text-2xl font-bold mt-6 mb-3" {...props} />
                        ),
                        h3: ({ node, ...props }) => (
                          <h3 className="text-xl font-bold mt-4 mb-2" {...props} />
                        ),
                      }}
                    >
                      {article.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="text-center py-12 text-muted-foreground">
                    <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>该文章暂无内容</p>
                    <Button
                      variant="outline"
                      className="mt-4"
                      onClick={() => refetchMutation.mutate()}
                      disabled={refetchMutation.isPending}
                    >
                      <RefreshCw className={`h-4 w-4 mr-2 ${refetchMutation.isPending ? "animate-spin" : ""}`} />
                      重新爬取
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* 图片展示 */}
            {(() => {
              const images = article.extra_data?.images
              if (!images || !Array.isArray(images) || images.length === 0) return null
              return (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <ImageIcon className="h-5 w-5" />
                      文章图片 ({images.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {images.map((imageUrl: unknown, index: number) => {
                        const url = String(imageUrl)
                        return (
                          <div key={index} className="group relative aspect-video rounded-lg overflow-hidden bg-muted">
                            <img
                              src={url}
                              alt={`图片 ${index + 1}`}
                              className="w-full h-full object-cover transition-transform group-hover:scale-105"
                              loading="lazy"
                            />
                            <a
                              href={url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white font-medium"
                            >
                              查看大图
                            </a>
                          </div>
                        )
                      })}
                    </div>
                  </CardContent>
                </Card>
              )
            })()}

            {/* 元数据 */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">文章信息</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-muted-foreground">创建时间</div>
                    <div>{formatDateTime(article.created_at)}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">更新时间</div>
                    <div>{formatDateTime(article.updated_at)}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">来源 ID</div>
                    <div>{article.source_id}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">状态</div>
                    <div>{getStatusBadge(article)}</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        ) : (
          <Card>
            <CardContent className="text-center py-12 text-muted-foreground">
              未找到文章
            </CardContent>
          </Card>
        )}
      </main>

      {/* 编辑对话框 */}
      <ArticleEditDialog
        article={currentArticle}
        open={editOpen}
        onOpenChange={setEditOpen}
      />
    </div>
  )
}
