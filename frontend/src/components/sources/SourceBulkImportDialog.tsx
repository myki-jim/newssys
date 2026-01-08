import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { sourcesApi } from "@/services/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Loader2, CheckCircle, XCircle, AlertCircle } from "lucide-react"

interface SourceBulkImportDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function SourceBulkImportDialog({ open, onOpenChange }: SourceBulkImportDialogProps) {
  const queryClient = useQueryClient()
  const [urls, setUrls] = useState("")
  const [results, setResults] = useState<{
    success_count: number
    failed_count: number
    errors: Array<{ url: string; error: string }>
  } | null>(null)

  const importMutation = useMutation({
    mutationFn: (baseUrls: string[]) =>
      sourcesApi.bulkCreate(
        baseUrls,
        // 默认解析器配置
        {
          title_selector: "h1",
          content_selector: "article, main",
          encoding: "utf-8",
        }
      ),
    onSuccess: (data) => {
      setResults({
        success_count: data.success_count,
        failed_count: data.failed_count,
        errors: data.errors as Array<{ url: string; error: string }>,
      })
      queryClient.invalidateQueries({ queryKey: ["sources"] })
    },
  })

  const handleImport = () => {
    const urlList = urls
      .split("\n")
      .map((url) => url.trim())
      .filter(Boolean)

    if (urlList.length === 0) return

    setResults(null)
    importMutation.mutate(urlList)
  }

  const handleReset = () => {
    setUrls("")
    setResults(null)
  }

  const handleClose = () => {
    handleReset()
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>批量导入采集源</DialogTitle>
          <DialogDescription>
            每行输入一个 URL，系统将自动识别站点名称并创建采集源配置。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {results ? (
            // 显示结果
            <div className="space-y-4">
              <div className="flex items-center justify-center gap-8 py-4">
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-6 w-6 text-green-500" />
                  <div>
                    <div className="text-2xl font-bold">{results.success_count}</div>
                    <div className="text-sm text-muted-foreground">成功</div>
                  </div>
                </div>
                {results.failed_count > 0 && (
                  <div className="flex items-center gap-2">
                    <XCircle className="h-6 w-6 text-destructive" />
                    <div>
                      <div className="text-2xl font-bold">{results.failed_count}</div>
                      <div className="text-sm text-muted-foreground">失败</div>
                    </div>
                  </div>
                )}
              </div>

              {results.errors.length > 0 && (
                <div className="max-h-60 overflow-y-auto rounded-md border p-4">
                  <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                    <AlertCircle className="h-4 w-4 text-destructive" />
                    错误详情
                  </div>
                  <ul className="space-y-2 text-sm">
                    {results.errors.map((error, i) => (
                      <li key={i} className="text-muted-foreground">
                        <span className="font-mono">{error.url}</span>
                        <span className="text-destructive ml-2">{error.error}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={handleReset}>
                  继续导入
                </Button>
                <Button onClick={handleClose}>完成</Button>
              </div>
            </div>
          ) : (
            // 输入表单
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="urls">URL 列表</Label>
                <textarea
                  id="urls"
                  className="flex min-h-[200px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  placeholder="https://example1.com&#10;https://example2.com&#10;https://example3.com"
                  value={urls}
                  onChange={(e) => setUrls(e.target.value)}
                  disabled={importMutation.isPending}
                />
                <p className="text-xs text-muted-foreground">
                  每行一个 URL，支持 http:// 和 https://
                </p>
              </div>

              <div className="rounded-md bg-muted p-3 text-sm">
                <p className="font-medium">默认配置：</p>
                <ul className="mt-1 space-y-1 text-muted-foreground">
                  <li>• 标题选择器：h1</li>
                  <li>• 内容选择器：article, main</li>
                  <li>• 编码：UTF-8</li>
                </ul>
              </div>
            </div>
          )}
        </div>

        {!results && (
          <DialogFooter>
            <Button variant="outline" onClick={handleClose}>
              取消
            </Button>
            <Button
              onClick={handleImport}
              disabled={importMutation.isPending || !urls.trim()}
            >
              {importMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              开始导入
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  )
}
