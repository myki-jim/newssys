import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { sourcesApi } from "@/services/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2, CheckCircle, XCircle, Clock } from "lucide-react"
import { formatDateTime } from "@/lib/utils"

interface SourceDebugDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  sourceId: number
}

export function SourceDebugDrawer({ open, onOpenChange, sourceId }: SourceDebugDrawerProps) {
  const queryClient = useQueryClient()
  const [testUrl, setTestUrl] = useState("")

  // 获取源详情
  const { data: source } = useQuery({
    queryKey: ["sources", sourceId],
    queryFn: () => sourcesApi.get(sourceId),
    enabled: open,
  })

  // 调试解析器
  const debugMutation = useMutation({
    mutationFn: (url: string) =>
      sourcesApi.debugParser(url, source?.parser_config || {}),
  })

  const handleTest = () => {
    if (!testUrl) return
    debugMutation.mutate(testUrl)
  }

  const result = debugMutation.data

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[600px] overflow-y-auto">
        <SheetHeader>
          <SheetTitle>配置调试器</SheetTitle>
          <SheetDescription>
            实时测试解析器配置，查看提取效果
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-6 py-4">
          {/* 当前配置 */}
          {source && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">当前配置</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="grid grid-cols-[100px_1fr] gap-2">
                  <span className="text-muted-foreground">站点:</span>
                  <span className="font-mono">{source.site_name}</span>

                  <span className="text-muted-foreground">标题:</span>
                  <span className="font-mono">{source.parser_config.title_selector}</span>

                  <span className="text-muted-foreground">内容:</span>
                  <span className="font-mono">{source.parser_config.content_selector}</span>

                  <span className="text-muted-foreground">时间:</span>
                  <span className="font-mono">
                    {source.parser_config.publish_time_selector || "(未设置)"}
                  </span>

                  <span className="text-muted-foreground">作者:</span>
                  <span className="font-mono">
                    {source.parser_config.author_selector || "(未设置)"}
                  </span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* 测试表单 */}
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="test-url">测试 URL</Label>
              <div className="flex gap-2">
                <Input
                  id="test-url"
                  placeholder="输入要测试的文章 URL..."
                  value={testUrl}
                  onChange={(e) => setTestUrl(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleTest()}
                />
                <Button
                  onClick={handleTest}
                  disabled={debugMutation.isPending || !testUrl}
                >
                  {debugMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    "测试"
                  )}
                </Button>
              </div>
            </div>

            {/* 快速填充 */}
            {source && (
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setTestUrl(`${source.base_url}/example-article`)}
                >
                  使用示例 URL
                </Button>
              </div>
            )}
          </div>

          {/* 测试结果 */}
          {result && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm">测试结果</CardTitle>
                  <div className="flex items-center gap-2">
                    {result.error ? (
                      <>
                        <XCircle className="h-4 w-4 text-destructive" />
                        <span className="text-sm text-destructive">失败</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle className="h-4 w-4 text-green-500" />
                        <span className="text-sm text-green-600">成功</span>
                      </>
                    )}
                    <span className="text-xs text-muted-foreground">
                      {result.extraction_time_ms}ms
                    </span>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {result.error ? (
                  <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                    {result.error}
                  </div>
                ) : (
                  <>
                    <div className="space-y-2">
                      <Label>标题</Label>
                      <div className="rounded-md bg-muted p-3 text-sm">
                        {result.title || "(未提取到)"}
                      </div>
                    </div>

                    {result.publish_time && (
                      <div className="space-y-2">
                        <Label>发布时间</Label>
                        <div className="rounded-md bg-muted p-3 text-sm">
                          <div className="flex items-center gap-2">
                            <Clock className="h-4 w-4 text-muted-foreground" />
                            {formatDateTime(result.publish_time)}
                          </div>
                        </div>
                      </div>
                    )}

                    {result.author && (
                      <div className="space-y-2">
                        <Label>作者</Label>
                        <div className="rounded-md bg-muted p-3 text-sm">
                          {result.author}
                        </div>
                      </div>
                    )}

                    <div className="space-y-2">
                      <Label>内容预览</Label>
                      <div className="max-h-[300px] overflow-y-auto rounded-md bg-muted p-3 text-sm">
                        <pre className="whitespace-pre-wrap font-sans">
                          {result.content
                            ? result.content.slice(0, 1000) +
                              (result.content.length > 1000 ? "..." : "")
                            : "(未提取到)"}
                        </pre>
                      </div>
                      {result.content && (
                        <div className="text-xs text-muted-foreground">
                          原始长度: {result.raw_html_length} 字符
                        </div>
                      )}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
