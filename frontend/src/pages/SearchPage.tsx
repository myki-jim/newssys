import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { searchApi } from "@/services/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Search, Globe, ExternalLink, Loader2, CheckCircle, Clock, Download } from "lucide-react"
import { formatDateTime, truncateText } from "@/lib/utils"
import type { SearchResult } from "@/types"

export function SearchPage() {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState("")
  const [timeRange, setTimeRange] = useState("w")
  const [results, setResults] = useState<SearchResult[] | null>(null)
  const [isSearching, setIsSearching] = useState(false)
  const [batchMode, setBatchMode] = useState(false)  // 批量保存模式开关

  // 搜索
  const searchMutation = useMutation({
    mutationFn: () =>
      searchApi.search(searchQuery, timeRange, 10),
    onSuccess: (data) => {
      setResults(data.results)
      setIsSearching(false)
    },
    onError: () => {
      setIsSearching(false)
    },
  })

  // 一键入库
  const saveMutation = useMutation({
    mutationFn: (result: SearchResult) =>
      searchApi.saveResult(result.url, result.title),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["articles"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard", "stats"] })
      alert("文章已保存到数据库！")
    },
  })

  // 批量保存
  const batchSaveMutation = useMutation({
    mutationFn: () =>
      searchApi.saveBatch(searchQuery, timeRange, 10),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["articles"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard", "stats"] })
      const { created, existing, failed, total } = data
      alert(`批量保存完成！\n总计: ${total}\n新保存: ${created}\n已存在: ${existing}\n失败: ${failed}`)
    },
  })

  const handleSearch = () => {
    if (!searchQuery) return
    setIsSearching(true)
    setResults(null)
    searchMutation.mutate()
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">联网搜索</h1>
        <p className="text-muted-foreground">
          搜索网络内容并一键入库到本地数据库
        </p>
      </div>

      {/* 搜索框 */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Search className="h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="输入搜索关键词..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                className="flex-1"
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">时间范围:</span>
                  <div className="flex gap-1">
                    {[
                      { value: "d", label: "一天" },
                      { value: "w", label: "一周" },
                      { value: "m", label: "一月" },
                      { value: "y", label: "一年" },
                    ].map((range) => (
                      <Button
                        key={range.value}
                        variant={timeRange === range.value ? "default" : "outline"}
                        size="sm"
                        onClick={() => setTimeRange(range.value)}
                      >
                        {range.label}
                      </Button>
                    ))}
                  </div>
                </div>

                {/* 批量保存开关 */}
                <div className="flex items-center gap-2 border-l pl-4">
                  <Switch
                    id="batch-mode"
                    checked={batchMode}
                    onCheckedChange={setBatchMode}
                  />
                  <Label htmlFor="batch-mode" className="text-sm cursor-pointer">
                    批量保存模式
                  </Label>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {/* 批量保存按钮 */}
                {batchMode && results && results.length > 0 && (
                  <Button
                    variant="default"
                    onClick={() => batchSaveMutation.mutate()}
                    disabled={batchSaveMutation.isPending}
                  >
                    {batchSaveMutation.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Download className="mr-2 h-4 w-4" />
                    )}
                    批量保存全部 ({results.length})
                  </Button>
                )}

                <Button
                  onClick={handleSearch}
                  disabled={isSearching || !searchQuery}
                >
                  {isSearching ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Search className="mr-2 h-4 w-4" />
                )}
                搜索
              </Button>
            </div>
          </div>
        </div>
        </CardContent>
      </Card>

      {/* 搜索结果 */}
      {results && (
        <Card>
          <CardHeader>
            <CardTitle>
              搜索结果 ({results.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {results.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                未找到相关结果
              </div>
            ) : (
              <div className="space-y-4">
                {results.map((result, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-4 p-4 rounded-lg border hover:bg-muted transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">{i + 1}.</span>
                        <a
                          href={result.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium hover:underline flex items-center gap-1"
                        >
                          {truncateText(result.title, 100)}
                          <ExternalLink className="h-3 w-3 shrink-0" />
                        </a>
                      </div>
                      <div className="text-sm text-muted-foreground mt-1 line-clamp-2">
                        {result.snippet}
                      </div>
                      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <Globe className="h-3 w-3" />
                          {result.source || "未知来源"}
                        </span>
                        {result.published_date && (
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatDateTime(result.published_date)}
                          </span>
                        )}
                      </div>
                    </div>
                    {/* 非批量模式显示单个保存按钮 */}
                    {!batchMode && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => saveMutation.mutate(result)}
                        disabled={saveMutation.isPending}
                      >
                        {saveMutation.isPending ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <>
                            <CheckCircle className="mr-2 h-4 w-4" />
                            一键入库
                          </>
                        )}
                      </Button>
                    )}
                    {/* 批量模式显示保存提示 */}
                    {batchMode && (
                      <div className="text-xs text-muted-foreground">
                        将批量保存
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* 初始状态提示 */}
      {!results && !isSearching && (
        <Card>
          <CardContent className="py-16">
            <div className="flex flex-col items-center justify-center text-center">
              <Search className="h-16 w-16 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">开始搜索</h3>
              <p className="text-muted-foreground max-w-md">
                输入关键词进行联网搜索，找到有用的文章后可以一键保存到本地数据库。
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
