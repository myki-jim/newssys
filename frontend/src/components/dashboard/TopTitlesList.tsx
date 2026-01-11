/**
 * 热门标题列表组件
 * 展示出现频次最高的标题（可能是热点新闻）
 */

import { TrendingUp } from "lucide-react"

interface TitleData {
  title: string
  count: number
}

interface TopTitlesListProps {
  data: TitleData[]
  limit?: number
}

export function TopTitlesList({ data, limit = 10 }: TopTitlesListProps) {
  const titles = data.slice(0, limit)

  if (!titles || titles.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-muted-foreground text-sm">
        暂无数据
      </div>
    )
  }

  const maxCount = Math.max(...titles.map((t) => t.count))

  return (
    <div className="space-y-2">
      {titles.map((item, index) => (
        <div key={index} className="flex items-center gap-3">
          <div className="flex-shrink-0 w-5 h-5 flex items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">
            {index + 1}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm truncate" title={item.title}>
              {item.title}
            </p>
            <div className="mt-1 h-1.5 w-full bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full"
                style={{ width: `${(item.count / maxCount) * 100}%` }}
              />
            </div>
          </div>
          <div className="flex-shrink-0 flex items-center gap-1 text-xs text-muted-foreground">
            <TrendingUp className="h-3 w-3" />
            <span className="font-medium">{item.count}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
