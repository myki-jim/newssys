import { useQuery } from "@tanstack/react-query"
import { reportsApi } from "@/services/api"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ExternalLink, Calendar, User, Globe, FileText } from "lucide-react"
import { formatDateTime } from "@/lib/utils"

interface CitationDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  reportId: string
  citationIndex: number
}

export function CitationDrawer({ open, onOpenChange, reportId, citationIndex }: CitationDrawerProps) {
  // 获取引用详情
  const { data: reference, isLoading } = useQuery({
    queryKey: ["reports", reportId, "references", citationIndex],
    queryFn: () => reportsApi.getReferenceDetail(reportId, citationIndex),
    enabled: open,
  })

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full max-w-2xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle>引用详情 [{citationIndex}]</SheetTitle>
          <SheetDescription>
            查看该引用的原始文章信息
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-6 py-4">
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            </div>
          ) : reference ? (
            <>
              {/* 文章基本信息 */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2">
                    <FileText className="h-4 w-4" />
                    基本信息
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-1">
                    <Label>标题</Label>
                    <div className="font-medium">{reference.article_title}</div>
                  </div>

                  <div className="space-y-1">
                    <Label>来源</Label>
                    <div className="flex items-center gap-2">
                      <Globe className="h-4 w-4 text-muted-foreground" />
                      <span>{reference.article_source}</span>
                    </div>
                  </div>

                  {reference.article_author && (
                    <div className="space-y-1">
                      <Label>作者</Label>
                      <div className="flex items-center gap-2">
                        <User className="h-4 w-4 text-muted-foreground" />
                        <span>{reference.article_author}</span>
                      </div>
                    </div>
                  )}

                  <div className="space-y-1">
                    <Label>发布时间</Label>
                    <div className="flex items-center gap-2">
                      <Calendar className="h-4 w-4 text-muted-foreground" />
                      <span>{formatDateTime(reference.article_publish_time)}</span>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <Label>原文链接</Label>
                    <Button variant="outline" size="sm" className="w-full" asChild>
                      <a
                        href={reference.article_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2"
                      >
                        <span className="truncate flex-1 text-left">
                          {reference.article_url}
                        </span>
                        <ExternalLink className="h-4 w-4 shrink-0" />
                      </a>
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* 引用上下文 */}
              {reference.context_snippet && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">引用上下文</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="rounded-md bg-muted p-4 text-sm">
                      {reference.context_snippet}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* 内容快照 */}
              {reference.article_content && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">内容快照</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="max-h-[400px] overflow-y-auto rounded-md bg-muted p-4 text-sm whitespace-pre-wrap">
                      {reference.article_content.slice(0, 2000)}
                      {reference.article_content.length > 2000 && "..."}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <div className="text-center text-muted-foreground py-8">
              未找到引用详情
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
