import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { sourcesApi } from "@/services/api"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ChevronRight, ChevronDown, File, Folder, Loader2 } from "lucide-react"
import { formatDateTime } from "@/lib/utils"

interface SourceSitemapDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  sourceId: number
}

interface SitemapNode {
  url: string
  lastmod: string | null
  children: SitemapNode[]
  depth: number
}

function SitemapTree({ node, depth = 0 }: { node: SitemapNode; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 2)
  const hasChildren = node.children && node.children.length > 0

  return (
    <div>
      <div
        className="flex items-center gap-1 py-1 text-sm"
        style={{ paddingLeft: `${depth * 16}px` }}
      >
        <button
          className="flex h-5 w-5 items-center justify-center rounded hover:bg-muted"
          onClick={() => setExpanded(!expanded)}
        >
          {hasChildren ? (
            expanded ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )
          ) : (
            <div className="h-3 w-3" />
          )}
        </button>
        {hasChildren ? (
          <Folder className="h-4 w-4 text-blue-500" />
        ) : (
          <File className="h-4 w-4 text-gray-400" />
        )}
        <span className="flex-1 truncate font-mono text-xs">
          {node.url.split("/").pop() || "/"}
        </span>
        {node.lastmod && (
          <span className="text-xs text-muted-foreground">
            {formatDateTime(node.lastmod)}
          </span>
        )}
      </div>
      {expanded && hasChildren && (
        <div>
          {node.children.map((child, i) => (
            <SitemapTree key={i} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

export function SourceSitemapDialog({ open, onOpenChange, sourceId }: SourceSitemapDialogProps) {
  const [maxDepth, setMaxDepth] = useState(3)

  const { data: sitemap, isLoading } = useQuery({
    queryKey: ["sources", sourceId, "sitemap", maxDepth],
    queryFn: async () => {
      const data = await sourcesApi.getSitemap(sourceId, maxDepth)
      // 转换 API 响应为 SitemapNode 类型（添加 depth 属性）
      const addDepth = (node: typeof data, depth = 0): SitemapNode => ({
        ...node,
        depth,
        children: (node.children || []).map(child => addDepth(child as any, depth + 1))
      })
      return addDepth(data)
    },
    enabled: open,
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle>Sitemap 浏览器</DialogTitle>
          <DialogDescription>
            查看源站点的 Sitemap 结构，递归深度: {maxDepth}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* 深度控制 */}
          <div className="flex items-center gap-4">
            <Label>递归深度:</Label>
            <div className="flex gap-1">
              {[1, 2, 3, 4, 5].map((d) => (
                <Button
                  key={d}
                  variant={maxDepth === d ? "default" : "outline"}
                  size="sm"
                  onClick={() => setMaxDepth(d)}
                >
                  {d}
                </Button>
              ))}
            </div>
          </div>

          {/* Sitemap 树 */}
          <div className="rounded-md border bg-muted/50 p-4">
            {isLoading ? (
              <div className="flex h-64 items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : sitemap ? (
              <div className="max-h-[500px] overflow-y-auto custom-scrollbar">
                <SitemapTree node={sitemap} />
              </div>
            ) : (
              <div className="flex h-64 items-center justify-center text-muted-foreground">
                暂无 Sitemap 数据
              </div>
            )}
          </div>

          {/* 统计 */}
          {sitemap && (
            <div className="flex gap-4 text-sm text-muted-foreground">
              <span>深度: {maxDepth}</span>
              <span>URL 数量: {countUrls(sitemap)}</span>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

function countUrls(node: SitemapNode): number {
  let count = 1
  for (const child of node.children) {
    count += countUrls(child)
  }
  return count
}
