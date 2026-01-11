import { useEffect, useRef, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Loader2, TrendingUp, Calendar, Filter, RotateCcw } from "lucide-react"
import { cn } from "@/lib/utils"
import type { KeywordCloudData } from "@/types"

interface KeywordCloudProps {
  data: KeywordCloudData[]
  loading?: boolean
  title?: string
  period?: string
  language?: string
  fromDate?: string
  toDate?: string
  totalArticles?: number
}

export function KeywordCloud({
  data,
  loading = false,
  title,
  period,
  language,
  fromDate,
  toDate,
  totalArticles,
}: KeywordCloudProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [hoveredKeyword, setHoveredKeyword] = useState<string | null>(null)

  // 归一化权重到字体大小范围
  const getFontSize = (weight: number) => {
    const minSize = 12
    const maxSize = 36
    return minSize + (weight / 100) * (maxSize - minSize)
  }

  // 根据权重获取颜色
  const getColor = (weight: number, index: number) => {
    const colors = [
      "text-primary",
      "text-blue-500",
      "text-green-500",
      "text-purple-500",
      "text-orange-500",
      "text-pink-500",
      "text-indigo-500",
      "text-teal-500",
      "text-red-500",
      "text-cyan-500",
    ]
    if (weight > 80) return colors[0]
    if (weight > 60) return colors[1]
    if (weight > 40) return colors[2]
    return colors[index % colors.length]
  }

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            {title || "关键词词云"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-48 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!data || data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            {title || "关键词词云"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-48 items-center justify-center text-muted-foreground text-sm">
            暂无数据
          </div>
        </CardContent>
      </Card>
    )
  }

  const periodLabel = period === "today" ? "今天" : period === "week" ? "本周" : "本月"
  const languageLabel = language === "zh" ? "中文" : "哈萨克语"

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <CardTitle className="text-sm">{title || "关键词词云"}</CardTitle>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Calendar className="h-3 w-3" />
            {periodLabel}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div
          ref={containerRef}
          className="flex min-h-48 flex-wrap items-center justify-center gap-2 p-4"
        >
          {data.map((item, index) => (
            <span
              key={item.keyword}
              className={cn(
                "cursor-pointer transition-all duration-200 hover:scale-110 hover:underline",
                getColor(item.weight, index)
              )}
              style={{
                fontSize: `${getFontSize(item.weight)}px`,
                fontWeight: item.weight > 70 ? "bold" : item.weight > 40 ? "medium" : "normal",
              }}
              onMouseEnter={() => setHoveredKeyword(item.keyword)}
              onMouseLeave={() => setHoveredKeyword(null)}
            >
              {item.keyword}
            </span>
          ))}
        </div>

        {/* 悬浮提示 */}
        {hoveredKeyword && (
          <div className="mt-2 text-xs text-muted-foreground text-center">
            {data.find((k) => k.keyword === hoveredKeyword)?.keyword} 权重:{" "}
            {data.find((k) => k.keyword === hoveredKeyword)?.weight?.toFixed(1)}
          </div>
        )}

        {/* 底部信息 */}
        <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground border-t pt-2">
          <span>{languageLabel}</span>
          <span>{totalArticles || 0} 篇文章</span>
        </div>
      </CardContent>
    </Card>
  )
}

// 词云网格组件（用于显示多个词云）
export function KeywordCloudGrid() {
  const [useCustomDate, setUseCustomDate] = useState(false)
  const [fromDate, setFromDate] = useState("")
  const [toDate, setToDate] = useState("")
  const [period, setPeriod] = useState<"today" | "week" | "month">("today")

  const { data: cloudData, loading, refetch } = useAllKeywordClouds(useCustomDate, fromDate, toDate, period)

  const clouds = [
    {
      key: `${period}-zh`,
      title: period === "today" ? "今天中文" : period === "week" ? "本周中文" : "本月中文",
      data: cloudData?.currentZh || [],
      period: period,
      language: "zh" as const,
    },
    {
      key: `${period}-kk`,
      title: period === "today" ? "今天哈萨克语" : period === "week" ? "本周哈萨克语" : "本月哈萨克语",
      data: cloudData?.currentKk || [],
      period: period,
      language: "kk" as const,
    },
  ]

  const handleApplyFilter = () => {
    refetch()
  }

  const handleResetFilter = () => {
    setFromDate("")
    setToDate("")
    setUseCustomDate(false)
    setTimeout(() => refetch(), 0)
  }

  return (
    <div className="space-y-4">
      {/* 日期筛选器 */}
      <div className="flex flex-wrap items-center gap-4 p-4 bg-muted/50 rounded-lg">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">时间范围:</span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setPeriod("today")}
            className={`px-3 py-1.5 text-sm rounded-md ${period === "today" ? "bg-primary text-primary-foreground" : "bg-background border"}`}
            disabled={useCustomDate}
          >
            今天
          </button>
          <button
            onClick={() => setPeriod("week")}
            className={`px-3 py-1.5 text-sm rounded-md ${period === "week" ? "bg-primary text-primary-foreground" : "bg-background border"}`}
            disabled={useCustomDate}
          >
            本周
          </button>
          <button
            onClick={() => setPeriod("month")}
            className={`px-3 py-1.5 text-sm rounded-md ${period === "month" ? "bg-primary text-primary-foreground" : "bg-background border"}`}
            disabled={useCustomDate}
          >
            本月
          </button>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="px-3 py-1.5 text-sm border rounded-md bg-background"
            disabled={!useCustomDate}
          />
          <span className="text-muted-foreground">至</span>
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className="px-3 py-1.5 text-sm border rounded-md bg-background"
            disabled={!useCustomDate}
          />
        </div>

        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={useCustomDate}
            onChange={(e) => setUseCustomDate(e.target.checked)}
            className="rounded"
          />
          <span>自定义</span>
        </label>

        <Button size="sm" onClick={handleApplyFilter} disabled={!useCustomDate || !fromDate || !toDate}>
          应用
        </Button>
        <Button size="sm" variant="outline" onClick={handleResetFilter} disabled={!useCustomDate}>
          <RotateCcw className="h-4 w-4 mr-1" />
          重置
        </Button>
      </div>

      {/* 词云网格 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {clouds.map((cloud) => (
          <KeywordCloud
            key={cloud.key}
            title={cloud.title}
            data={cloud.data}
            loading={loading}
            period={cloud.period}
            language={cloud.language}
          />
        ))}
      </div>
    </div>
  )
}

// Hook 获取所有词云数据
function useAllKeywordClouds(useCustomDate: boolean, fromDate: string, toDate: string, period: "today" | "week" | "month") {
  const [data, setData] = useState<{
    currentZh: KeywordCloudData[]
    currentKk: KeywordCloudData[]
  }>({
    currentZh: [],
    currentKk: [],
  })
  const [loading, setLoading] = useState(true)
  const [, setRefetchFlag] = useState(0)

  const fetchAllClouds = async () => {
    setLoading(true)
    try {
      const API_BASE = "/api/v1"
      const params = useCustomDate && fromDate && toDate
        ? `period=custom&from_date=${fromDate}&to_date=${toDate}`
        : `period=${period}`

      const [currentZh, currentKk] = await Promise.all([
        fetch(`${API_BASE}/dashboard/keywords/cloud?${params}&language=zh`).then((r) => r.json()),
        fetch(`${API_BASE}/dashboard/keywords/cloud?${params}&language=kk`).then((r) => r.json()),
      ])

      setData({
        currentZh: currentZh.success ? (currentZh.data?.keywords || []) : [],
        currentKk: currentKk.success ? (currentKk.data?.keywords || []) : [],
      })
    } catch (error) {
      console.error("Failed to fetch keyword clouds:", error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAllClouds()
  }, [useCustomDate, fromDate, toDate, period])

  return { data, loading, refetch: () => setRefetchFlag((prev) => prev + 1) }
}
