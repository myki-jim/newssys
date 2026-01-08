import { useState, useEffect } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { articlesApi } from "@/services/api"
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
import { Textarea } from "@/components/ui/textarea"
import { Loader2 } from "lucide-react"
import { formatDateTime } from "@/lib/utils"
import type { Article } from "@/types"

interface ArticleEditDialogProps {
  article: Article | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function ArticleEditDialog({
  article,
  open,
  onOpenChange,
}: ArticleEditDialogProps) {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState(article?.title || "")
  const [content, setContent] = useState(article?.content || "")
  const [publishTime, setPublishTime] = useState(
    article?.publish_time ? new Date(article.publish_time).toISOString().slice(0, 16) : ""
  )
  const [author, setAuthor] = useState(article?.author || "")

  // 当 article 变化时重置表单
  useEffect(() => {
    if (article) {
      setTitle(article.title)
      setContent(article.content || "")
      setPublishTime(
        article.publish_time ? new Date(article.publish_time).toISOString().slice(0, 16) : ""
      )
      setAuthor(article.author || "")
    } else {
      setTitle("")
      setContent("")
      setPublishTime("")
      setAuthor("")
    }
  }, [article])

  const updateMutation = useMutation({
    mutationFn: (data: { title?: string; content?: string; publish_time?: string; author?: string }) =>
      articlesApi.update(article!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["articles"] })
      queryClient.invalidateQueries({ queryKey: ["article", article?.id] })
      onOpenChange(false)
    },
  })

  const handleSubmit = () => {
    if (!article) return

    updateMutation.mutate({
      title: title !== article.title ? title : undefined,
      content: content !== article.content ? content : undefined,
      publish_time: publishTime ? new Date(publishTime).toISOString() : undefined,
      author: author !== article.author ? author : undefined,
    })
  }

  if (!article) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>编辑文章</DialogTitle>
          <DialogDescription>
            编辑文章标题、内容、发布时间和作者信息
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          <div className="space-y-2">
            <Label htmlFor="title">标题 *</Label>
            <Input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="输入文章标题"
              disabled={updateMutation.isPending}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="author">作者</Label>
            <Input
              id="author"
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              placeholder="输入作者名称（可选）"
              disabled={updateMutation.isPending}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="publishTime">发布时间</Label>
            <Input
              id="publishTime"
              type="datetime-local"
              value={publishTime}
              onChange={(e) => setPublishTime(e.target.value)}
              disabled={updateMutation.isPending}
            />
            <p className="text-xs text-muted-foreground">
              原发布时间: {formatDateTime(article.publish_time)}
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="content">内容</Label>
            <Textarea
              id="content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="输入文章内容（支持 Markdown）"
              rows={15}
              className="font-mono text-sm"
              disabled={updateMutation.isPending}
            />
            <p className="text-xs text-muted-foreground">
              {content.length} 个字符
            </p>
          </div>

          {/* 原始 URL */}
          <div className="space-y-2">
            <Label>原始 URL</Label>
            <p className="text-sm text-muted-foreground break-all">
              {article.url}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(article.url, "_blank")}
              className="w-full"
            >
              在新窗口打开原始链接
            </Button>
          </div>

          {/* 元数据 */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-muted-foreground">文章 ID:</span> {article.id}
            </div>
            <div>
              <span className="text-muted-foreground">来源 ID:</span> {article.source_id}
            </div>
            <div>
              <span className="text-muted-foreground">状态:</span> {article.status}
            </div>
            <div>
              <span className="text-muted-foreground">采集时间:</span>{" "}
              {formatDateTime(article.crawled_at)}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={updateMutation.isPending}
          >
            取消
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={updateMutation.isPending || !title}
          >
            {updateMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                保存中...
              </>
            ) : (
              "保存更改"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
