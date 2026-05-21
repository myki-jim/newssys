import { Star, ExternalLink, Calendar, Globe } from "lucide-react"
import { useState } from "react"

// 模拟星标文章数据 — 后续可接入后端 API
const MOCK_STARRED = [
  {
    id: 1,
    title: "全球网络安全态势年度报告 2025",
    source: "安全内参",
    publish_date: "2026-05-15",
    url: "https://example.com/article-1",
  },
  {
    id: 2,
    title: "AI 驱动的开源情报分析技术综述",
    source: "情报学报",
    publish_date: "2026-05-10",
    url: "https://example.com/article-2",
  },
]

export function StarredArticlesPage() {
  const [starred] = useState(MOCK_STARRED)

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold">星标文章</h2>
        <p className="text-muted-foreground mt-1">已收藏的重要文章</p>
      </div>

      {starred.length === 0 ? (
        <div className="text-center py-20 text-muted-foreground">
          <Star className="h-12 w-12 mx-auto mb-4 opacity-30" />
          <p>暂无星标文章</p>
          <p className="text-sm mt-1">在文章库中点击星标图标即可收藏</p>
        </div>
      ) : (
        <div className="space-y-3">
          {starred.map((article) => (
            <div
              key={article.id}
              className="flex items-start gap-4 rounded-lg border bg-card p-4 hover:shadow-sm transition-shadow"
            >
              <button className="mt-0.5 shrink-0">
                <Star className="h-5 w-5 fill-yellow-400 text-yellow-400" />
              </button>
              <div className="flex-1 min-w-0">
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-medium hover:text-primary transition-colors line-clamp-2"
                >
                  {article.title}
                </a>
                <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Globe className="h-3 w-3" />
                    {article.source}
                  </span>
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    {article.publish_date}
                  </span>
                </div>
              </div>
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 text-muted-foreground hover:text-primary transition-colors"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
