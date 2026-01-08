import { useState, useEffect, useRef } from "react"
import { useQuery } from "@tanstack/react-query"
import { useParams, useNavigate } from "react-router-dom"
import { reportsApi } from "@/services/api"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  ArrowLeft,
  Calendar,
  Hash,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  Layers,
  FileText,
  Download,
  Share2,
  Image as ImageIcon,
  RefreshCw,
  Sparkles,
} from "lucide-react"
import { formatDateTime } from "@/lib/utils"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeRaw from "rehype-raw"
import rehypeSanitize from "rehype-sanitize"
import type { Report, ReportSSEEvent } from "@/types"

const AUTO_REFRESH_INTERVAL = 3000 // 3秒自动刷新（详情页更快）

export function ReportDetailPage() {
  const { reportId } = useParams<{ reportId: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState("content")

  // 流式生成状态
  const [currentStreamingSection, setCurrentStreamingSection] = useState<{
    title: string
    content: string
  } | null>(null)
  const [liveSections, setLiveSections] = useState<Report["sections"]>([])
  const [agentMessage, setAgentMessage] = useState<string>("")
  const [agentProgress, setAgentProgress] = useState<number>(0)
  const [isReconnecting, setIsReconnecting] = useState(false)
  const sseConnectionRef = useRef<EventSource | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const streamingContentRef = useRef<HTMLDivElement>(null)

  // 获取报告详情
  const { data: report, isLoading, refetch } = useQuery({
    queryKey: ["reports", reportId],
    queryFn: () => reportsApi.get(Number(reportId)),
    enabled: !!reportId,
    // 正在生成的报告自动刷新
    refetchInterval: (data) => {
      return data?.status === "generating" ? AUTO_REFRESH_INTERVAL : false
    },
  })

  // 当报告在生成状态时，建立SSE连接接收实时更新
  useEffect(() => {
    if (!reportId) return

    // 清理函数
    const cleanup = () => {
      if (sseConnectionRef.current) {
        sseConnectionRef.current.close()
        sseConnectionRef.current = null
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      setIsReconnecting(false)
    }

    // 如果不在生成状态，清理并返回
    if (report?.status !== "generating") {
      cleanup()
      return
    }

    // 避免重复连接
    if (sseConnectionRef.current) {
      return
    }

    // 建立SSE连接
    console.log("建立SSE连接:", reportId)
    const eventSource = new EventSource(`/api/v1/reports/${reportId}/stream`)
    sseConnectionRef.current = eventSource

    // 处理打开事件
    eventSource.onopen = () => {
      console.log("SSE连接已建立")
      setIsReconnecting(false)
    }

    // 处理消息
    eventSource.addEventListener("state", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        console.log("收到状态更新:", data)
        // 更新进度
        if (data.data?.sections) {
          setLiveSections(data.data.sections)
        }
        if (data.message) {
          setAgentMessage(data.message)
        }
        if (data.progress !== undefined) {
          setAgentProgress(data.progress)
        }
      } catch (err) {
        console.error("解析SSE消息失败:", err)
      }
    })

    // 处理流式输出
    eventSource.addEventListener("section_stream", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data)
        console.log("收到流式内容:", data.section_title, data.chunk?.substring(0, 50))
        setCurrentStreamingSection({
          title: data.section_title,
          content: data.accumulated_content,
        })
        // 自动滚动到底部
        setTimeout(() => {
          if (streamingContentRef.current) {
            streamingContentRef.current.scrollTop = streamingContentRef.current.scrollHeight
          }
        }, 50)
      } catch (err) {
        console.error("解析流式输出失败:", err)
      }
    })

    // 处理完成
    eventSource.addEventListener("complete", (e: MessageEvent) => {
      console.log("报告生成完成")
      setCurrentStreamingSection(null)
      setIsReconnecting(false)
      refetch()
      cleanup()
    })

    // 处理错误
    eventSource.addEventListener("error", (e: MessageEvent) => {
      console.error("SSE错误:", e)
      cleanup()
      // 如果报告仍在生成，尝试重连
      if (report?.status === "generating") {
        setIsReconnecting(true)
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log("尝试重连...")
          sseConnectionRef.current = null
          // 触发重新建立连接
          refetch()
        }, 3000)
      }
    })

    // 清理
    return () => {
      cleanup()
    }
  }, [reportId, report?.status, refetch])

  // 合并已完成和正在生成的板块
  const displaySections = report?.sections || liveSections

  const getStatusBadge = (status: Report["status"]) => {
    switch (status) {
      case "completed":
        return (
          <Badge variant="outline" className="gap-1 bg-green-100 text-green-700 border-green-200 dark:bg-green-900 dark:text-green-300 dark:border-green-800">
            <CheckCircle className="h-3 w-3" />
            已完成
          </Badge>
        )
      case "generating":
        return (
          <Badge variant="outline" className="gap-1 bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900 dark:text-blue-300 dark:border-blue-800">
            <Loader2 className="h-3 w-3 animate-spin" />
            生成中
          </Badge>
        )
      case "draft":
        return (
          <Badge variant="outline" className="gap-1 bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-900 dark:text-yellow-300 dark:border-yellow-800">
            <Clock className="h-3 w-3" />
            草稿
          </Badge>
        )
      case "failed":
        return (
          <Badge variant="outline" className="gap-1 bg-red-100 text-red-700 border-red-200 dark:bg-red-900 dark:text-red-300 dark:border-red-800">
            <XCircle className="h-3 w-3" />
            失败
          </Badge>
        )
      default:
        return null
    }
  }

  const formatTimeRange = (start: string, end: string) => {
    const startDate = new Date(start)
    const endDate = new Date(end)
    return `${startDate.toLocaleDateString("zh-CN")} - ${endDate.toLocaleDateString("zh-CN")}`
  }

  const handleExport = () => {
    if (!report?.content) return

    // 创建纯文本版本
    const blob = new Blob([report.content], { type: "text/markdown;charset=utf-8" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${report.title}.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleShare = async () => {
    if (!report) return

    if (navigator.share) {
      try {
        await navigator.share({
          title: report.title,
          text: `查看报告：${report.title}`,
          url: window.location.href,
        })
      } catch (error) {
        console.log("分享失败:", error)
      }
    } else {
      // 复制链接
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
                <h1 className="text-xl font-bold truncate">
                  {report?.title || "报告详情"}
                </h1>
                {report && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground mt-1">
                    <span>{formatDateTime(report.created_at)}</span>
                    <span>·</span>
                    <span>{report.total_articles} 篇文章</span>
                  </div>
                )}
              </div>
            </div>
            {report?.status === "completed" && (
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={handleShare}>
                  <Share2 className="h-4 w-4 mr-2" />
                  分享
                </Button>
                <Button variant="outline" size="sm" onClick={handleExport}>
                  <Download className="h-4 w-4 mr-2" />
                  导出
                </Button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* 主要内容 */}
      <main className="container mx-auto px-4 py-8 max-w-5xl">
        {isLoading ? (
          <div className="flex h-64 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        ) : report ? (
          <div className="space-y-6">
            {/* 报告元信息卡片 */}
            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-wrap items-center gap-4 text-sm">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">时间范围：</span>
                    <span>{formatTimeRange(report.time_range_start, report.time_range_end)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Hash className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">文章数：</span>
                    <span>{report.total_articles} 篇</span>
                    {report.clustered_articles > 0 && (
                      <span className="text-muted-foreground">
                        → {report.clustered_articles} 篇
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Layers className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">事件数：</span>
                    <span>{report.event_count} 个</span>
                  </div>
                  {getStatusBadge(report.status)}
                  {report.language && (
                    <Badge variant="secondary" className="text-xs">
                      {report.language === "zh" ? "中文" : "哈萨克语"}
                    </Badge>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* 生成中或失败的提示 */}
            {report.status === "generating" && (
              <>
                <Card>
                  <CardContent className="py-12">
                    <div className="text-center">
                      <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto mb-4" />
                      <p className="text-lg font-medium">报告生成中...</p>
                      <p className="text-sm text-muted-foreground mt-2">
                        {agentMessage || report.agent_message || "正在处理"}
                      </p>
                      {isReconnecting && (
                        <p className="text-xs text-orange-500 mt-2 flex items-center justify-center gap-1">
                          <RefreshCw className="h-3 w-3 animate-spin" />
                          正在重新连接...
                        </p>
                      )}
                      <div className="mt-4 h-2 max-w-md mx-auto rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full rounded-full bg-primary transition-all duration-300"
                          style={{ width: `${agentProgress || report.agent_progress}%` }}
                        />
                      </div>
                      <p className="text-sm text-muted-foreground mt-2">
                        {agentProgress || report.agent_progress}%
                      </p>
                    </div>
                  </CardContent>
                </Card>

                {/* AI 实时生成内容 */}
                {currentStreamingSection && (
                  <Card className="border-primary/50 shadow-lg">
                    <CardHeader className="bg-primary/5">
                      <CardTitle className="flex items-center gap-2">
                        <Sparkles className="h-5 w-5 animate-pulse text-primary" />
                        正在生成：{currentStreamingSection.title}
                        <Loader2 className="h-4 w-4 animate-spin text-primary ml-auto" />
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="pt-6">
                      <div
                        ref={streamingContentRef}
                        className="max-h-[600px] overflow-y-auto rounded-md bg-muted/30 p-6"
                      >
                        <div className="prose prose-lg max-w-none dark:prose-invert">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            rehypePlugins={[rehypeRaw, rehypeSanitize]}
                          >
                            {currentStreamingSection.content || "正在生成内容..."}
                          </ReactMarkdown>
                        </div>
                      </div>
                      <p className="mt-4 text-sm text-muted-foreground flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-primary animate-pulse" />
                        AI 正在实时生成内容，您可以看到完整的写作过程
                      </p>
                    </CardContent>
                  </Card>
                )}

                {/* 已完成的板块预览 */}
                {displaySections.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm flex items-center gap-2">
                        <Layers className="h-4 w-4" />
                        已完成板块 ({displaySections.length})
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {displaySections.map((section, index) => (
                          <div
                            key={index}
                            className="flex items-center justify-between p-3 rounded-md bg-muted/50"
                          >
                            <span className="font-medium">{section.title}</span>
                            <span className="text-sm text-muted-foreground">
                              {section.event_count} 个事件
                            </span>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </>
            )}

            {report.status === "failed" && (
              <Card>
                <CardContent className="py-12">
                  <div className="text-center">
                    <XCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
                    <p className="text-lg font-medium text-destructive">报告生成失败</p>
                    {report.error_message && (
                      <p className="text-sm text-muted-foreground mt-2">{report.error_message}</p>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* 报告内容 */}
            {report.status === "completed" && report.content && (
              <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                <TabsList className="grid w-full max-w-md grid-cols-2">
                  <TabsTrigger value="content">
                    <FileText className="h-4 w-4 mr-2" />
                    完整报告
                  </TabsTrigger>
                  <TabsTrigger value="sections">
                    <Layers className="h-4 w-4 mr-2" />
                    板块详情
                  </TabsTrigger>
                </TabsList>

                {/* 完整报告 */}
                <TabsContent value="content" className="mt-6">
                  <Card>
                    <CardContent className="pt-6">
                      <div className="prose-markdown dark:prose-invert">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          rehypePlugins={[rehypeRaw, rehypeSanitize]}
                          components={{
                            // 自定义图片渲染
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
                            // 自定义标题样式
                            h1: ({ node, ...props }) => (
                              <h1 className="text-3xl font-bold mt-8 mb-4 first:mt-0" {...props} />
                            ),
                            h2: ({ node, ...props }) => (
                              <h2 className="text-2xl font-bold mt-6 mb-3" {...props} />
                            ),
                            h3: ({ node, ...props }) => (
                              <h3 className="text-xl font-bold mt-4 mb-2" {...props} />
                            ),
                            // 自定义列表样式
                            ul: ({ node, ...props }) => (
                              <ul className="list-disc list-inside my-4 space-y-2" {...props} />
                            ),
                            ol: ({ node, ...props }) => (
                              <ol className="list-decimal list-inside my-4 space-y-2" {...props} />
                            ),
                            // 自定义引用样式
                            blockquote: ({ node, ...props }) => (
                              <blockquote className="border-l-4 border-primary pl-4 italic my-4 text-muted-foreground" {...props} />
                            ),
                            // 自定义代码块样式
                            code: ({ node, inline, ...props }) =>
                              inline ? (
                                <code className="bg-muted px-1.5 py-0.5 rounded text-sm font-mono" {...props} />
                              ) : (
                                <code className="block bg-muted p-4 rounded-lg text-sm font-mono overflow-x-auto my-4" {...props} />
                              ),
                          }}
                        >
                          {report.content}
                        </ReactMarkdown>
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>

                {/* 板块详情 */}
                <TabsContent value="sections" className="mt-6 space-y-6">
                  {report.sections && report.sections.length > 0 ? (
                    report.sections.map((section, index) => (
                      <Card key={index}>
                        <CardHeader>
                          <div className="flex items-start justify-between">
                            <div>
                              <CardTitle className="text-2xl">{section.title}</CardTitle>
                              {section.description && (
                                <p className="text-muted-foreground mt-2">{section.description}</p>
                              )}
                            </div>
                            <Badge variant="secondary" className="shrink-0">
                              {section.event_count} 个事件
                            </Badge>
                          </div>
                        </CardHeader>
                        <CardContent>
                          <div className="prose-markdown dark:prose-invert">
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              rehypePlugins={[rehypeRaw, rehypeSanitize]}
                              components={{
                                img: ({ node, ...props }) => (
                                  <div className="my-6">
                                    <img
                                      {...props}
                                      className="rounded-lg shadow-lg max-h-[500px] w-auto mx-auto"
                                      alt={props.alt || "图片"}
                                      loading="lazy"
                                    />
                                  </div>
                                ),
                              }}
                            >
                              {section.content}
                            </ReactMarkdown>
                          </div>
                        </CardContent>
                      </Card>
                    ))
                  ) : (
                    <Card>
                      <CardContent className="text-center py-12 text-muted-foreground">
                        暂无板块
                      </CardContent>
                    </Card>
                  )}
                </TabsContent>
              </Tabs>
            )}

            {/* 报告统计信息 */}
            {report.status === "completed" && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">报告信息</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-6 text-sm">
                    <div>
                      <div className="text-muted-foreground">创建时间</div>
                      <div className="font-medium">{formatDateTime(report.created_at)}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">完成时间</div>
                      <div className="font-medium">{formatDateTime(report.completed_at)}</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">总文章数</div>
                      <div className="font-medium">{report.total_articles} 篇</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">去重后</div>
                      <div className="font-medium">{report.clustered_articles} 篇</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">重点事件</div>
                      <div className="font-medium">{report.event_count} 个</div>
                    </div>
                    <div>
                      <div className="text-muted-foreground">板块数量</div>
                      <div className="font-medium">{report.sections?.length || 0} 个</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        ) : (
          <Card>
            <CardContent className="text-center py-12 text-muted-foreground">
              未找到报告
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  )
}
