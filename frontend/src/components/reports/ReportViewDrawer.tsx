import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { reportsApi } from "@/services/api"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  FileText,
  Calendar,
  Hash,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  Layers,
} from "lucide-react"
import { formatDateTime } from "@/lib/utils"
import ReactMarkdown from "react-markdown"
import type { Report } from "@/types"

interface ReportViewDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  reportId: number
}

export function ReportViewDrawer({ open, onOpenChange, reportId }: ReportViewDrawerProps) {
  // 获取报告详情
  const { data: report, isLoading } = useQuery({
    queryKey: ["reports", reportId],
    queryFn: () => reportsApi.get(reportId),
    enabled: open,
  })

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

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full max-w-5xl overflow-y-auto">
        <SheetHeader>
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <SheetTitle className="text-xl">{report?.title || "报告详情"}</SheetTitle>
              <SheetDescription className="mt-2">
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  {report && (
                    <>
                      <div className="flex items-center gap-1">
                        <Calendar className="h-3.5 w-3.5" />
                        {formatTimeRange(report.time_range_start, report.time_range_end)}
                      </div>
                      <div className="flex items-center gap-1">
                        <Hash className="h-3.5 w-3.5" />
                        {report.total_articles} 篇文章
                        {report.clustered_articles > 0 && (
                          <span className="text-muted-foreground">
                            → {report.clustered_articles} 篇
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1">
                        <Layers className="h-3.5 w-3.5" />
                        {report.event_count} 个事件
                      </div>
                      {getStatusBadge(report.status)}
                      {report.language && (
                        <Badge variant="secondary" className="text-xs">
                          {report.language === "zh" ? "中文" : "哈萨克语"}
                        </Badge>
                      )}
                    </>
                  )}
                </div>
              </SheetDescription>
            </div>
          </div>
        </SheetHeader>

        <div className="py-4">
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : report ? (
            <Tabs defaultValue="content" className="w-full">
              <TabsList className="grid w-full max-w-md grid-cols-2">
                <TabsTrigger value="content">报告内容</TabsTrigger>
                <TabsTrigger value="sections">板块详情</TabsTrigger>
              </TabsList>

              <TabsContent value="content" className="mt-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <FileText className="h-4 w-4" />
                      完整报告
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {report.status === "generating" ? (
                      <div className="text-center py-8">
                        <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto mb-4" />
                        <p className="text-muted-foreground">报告生成中...</p>
                        <div className="mt-2 text-sm text-muted-foreground">
                          当前阶段: {report.agent_message || "初始化"}
                        </div>
                        <div className="mt-4 h-2 max-w-xs mx-auto rounded-full bg-muted overflow-hidden">
                          <div
                            className="h-full rounded-full bg-primary transition-all duration-300"
                            style={{ width: `${report.agent_progress}%` }}
                          />
                        </div>
                      </div>
                    ) : report.status === "failed" ? (
                      <div className="text-center py-8">
                        <XCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
                        <p className="text-destructive font-medium">报告生成失败</p>
                        {report.error_message && (
                          <p className="text-sm text-muted-foreground mt-2">{report.error_message}</p>
                        )}
                      </div>
                    ) : report.status === "draft" ? (
                      <div className="text-center py-8">
                        <Clock className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                        <p className="text-muted-foreground">报告尚未生成</p>
                      </div>
                    ) : report.content ? (
                      <div className="prose prose-sm max-w-none dark:prose-invert">
                        <ReactMarkdown>{report.content}</ReactMarkdown>
                      </div>
                    ) : (
                      <div className="text-center text-muted-foreground py-8">
                        该报告暂无内容
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="sections" className="mt-4">
                {report.sections && report.sections.length > 0 ? (
                  <div className="space-y-4">
                    {report.sections.map((section, index) => (
                      <Card key={index}>
                        <CardHeader>
                          <div className="flex items-start justify-between">
                            <CardTitle className="text-lg">{section.title}</CardTitle>
                            <Badge variant="secondary" className="text-xs">
                              {section.event_count} 个事件
                            </Badge>
                          </div>
                          {section.description && (
                            <p className="text-sm text-muted-foreground mt-1">{section.description}</p>
                          )}
                        </CardHeader>
                        <CardContent>
                          <div className="prose prose-sm max-w-none dark:prose-invert">
                            <ReactMarkdown>{section.content}</ReactMarkdown>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : (
                  <Card>
                    <CardContent className="text-center py-8 text-muted-foreground">
                      {report.status === "generating"
                        ? "板块生成中..."
                        : report.status === "draft"
                          ? "等待生成..."
                          : "暂无板块"}
                    </CardContent>
                  </Card>
                )}
              </TabsContent>
            </Tabs>
          ) : (
            <div className="text-center text-muted-foreground py-8">
              未找到报告
            </div>
          )}

          {/* 报告元数据 */}
          {report && report.status === "completed" && (
            <Card className="mt-4">
              <CardHeader>
                <CardTitle className="text-sm">报告信息</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-muted-foreground">创建时间</div>
                    <div>{formatDateTime(report.created_at)}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">完成时间</div>
                    <div>{formatDateTime(report.completed_at)}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">总文章数</div>
                    <div>{report.total_articles} 篇</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">去重后</div>
                    <div>{report.clustered_articles} 篇</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">重点事件</div>
                    <div>{report.event_count} 个</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">板块数量</div>
                    <div>{report.sections?.length || 0} 个</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
