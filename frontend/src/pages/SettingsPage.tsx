import { useState, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { Save, RotateCcw } from "lucide-react"

// 设置类型定义
interface Settings {
  // AI 设置
  ai_provider: "openai" | "anthropic" | "ollama"
  ai_model: string
  api_key: string
  api_url: string

  // 搜索设置
  default_search_count: number
  search_time_range: string
  search_region: string

  // 爬虫设置
  crawl_concurrent: number
  crawl_delay: number
  crawl_timeout: number
  crawl_retry_count: number

  // Sitemap 设置
  sitemap_recursive: boolean
  sitemap_follow_alternates: boolean

  // 其他设置
  max_article_length: number
  min_article_length: number
}

const defaultSettings: Settings = {
  ai_provider: "openai",
  ai_model: "gpt-4o-mini",
  api_key: "",
  api_url: "",

  default_search_count: 10,
  search_time_range: "w",
  search_region: "cn-zh",

  crawl_concurrent: 3,
  crawl_delay: 1,
  crawl_timeout: 30,
  crawl_retry_count: 2,

  sitemap_recursive: true,
  sitemap_follow_alternates: true,

  max_article_length: 50000,
  min_article_length: 50,
}

// AI 模型选项
const aiModels = {
  openai: ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
  anthropic: ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307", "claude-3-opus-20240229"],
  ollama: ["llama3.2", "mistral", "qwen2.5"],
}

export default function SettingsPage() {
  const queryClient = useQueryClient()
  const [settings, setSettings] = useState<Settings>(defaultSettings)
  const [hasChanges, setHasChanges] = useState(false)

  // 获取设置
  const { data: currentSettings, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: async () => {
      // TODO: 调用 API 获取设置
      // const res = await fetch("/api/v1/settings")
      // return await res.json()
      return defaultSettings
    },
  })

  useEffect(() => {
    if (currentSettings) {
      setSettings(currentSettings)
    }
  }, [currentSettings])

  // 更新设置
  const saveMutation = useMutation({
    mutationFn: async (newSettings: Settings) => {
      // TODO: 调用 API 保存设置
      // const res = await fetch("/api/v1/settings", {
      //   method: "PUT",
      //   headers: { "Content-Type": "application/json" },
      //   body: JSON.stringify(newSettings),
      // })
      // return await res.json()
      await new Promise((resolve) => setTimeout(resolve, 500))
      return { success: true }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] })
      setHasChanges(false)
      alert("设置已保存")
    },
    onError: () => {
      alert("保存失败，请重试")
    },
  })

  const handleSave = () => {
    saveMutation.mutate(settings)
  }

  const handleReset = () => {
    setSettings(defaultSettings)
    setHasChanges(true)
    alert("设置已重置为默认值")
  }

  const updateSetting = <K extends keyof Settings>(key: K, value: Settings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }))
    setHasChanges(true)
  }

  if (isLoading) {
    return <div className="flex items-center justify-center h-96">加载中...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">系统设置</h1>
          <p className="text-muted-foreground">配置系统参数和偏好设置</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleReset} disabled={!hasChanges}>
            <RotateCcw className="mr-2 h-4 w-4" />
            重置
          </Button>
          <Button onClick={handleSave} disabled={!hasChanges || saveMutation.isPending}>
            <Save className="mr-2 h-4 w-4" />
            {saveMutation.isPending ? "保存中..." : "保存设置"}
          </Button>
        </div>
      </div>

      {/* AI 设置 */}
      <Card>
        <CardHeader>
          <CardTitle>AI 设置</CardTitle>
          <CardDescription>配置 AI 模型和 API（留空则使用环境变量）</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="ai-provider">AI 提供商</Label>
              <Select
                value={settings.ai_provider}
                onValueChange={(value: "openai" | "anthropic" | "ollama") => updateSetting("ai_provider", value)}
              >
                <SelectTrigger id="ai-provider">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="openai">OpenAI</SelectItem>
                  <SelectItem value="anthropic">Anthropic</SelectItem>
                  <SelectItem value="ollama">Ollama</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="ai-model">模型</Label>
              <Select
                value={settings.ai_model}
                onValueChange={(value) => updateSetting("ai_model", value)}
              >
                <SelectTrigger id="ai-model">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {aiModels[settings.ai_provider].map((model) => (
                    <SelectItem key={model} value={model}>
                      {model}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="api-key">API Key（留空使用环境变量）</Label>
            <Input
              id="api-key"
              type="password"
              value={settings.api_key}
              onChange={(e) => updateSetting("api_key", e.target.value)}
              placeholder="sk-..."
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="api-url">API URL（留空使用默认地址）</Label>
            <Input
              id="api-url"
              value={settings.api_url}
              onChange={(e) => updateSetting("api_url", e.target.value)}
              placeholder="https://api.openai.com/v1"
            />
          </div>
        </CardContent>
      </Card>

      {/* 搜索设置 */}
      <Card>
        <CardHeader>
          <CardTitle>搜索设置</CardTitle>
          <CardDescription>配置联网搜索的默认参数</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="search-count">默认搜索数量</Label>
              <Input
                id="search-count"
                type="number"
                min={1}
                max={100}
                value={settings.default_search_count}
                onChange={(e) => updateSetting("default_search_count", parseInt(e.target.value) || 10)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="time-range">时间范围</Label>
              <Select
                value={settings.search_time_range}
                onValueChange={(value) => updateSetting("search_time_range", value)}
              >
                <SelectTrigger id="time-range">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="d">24小时内</SelectItem>
                  <SelectItem value="w">一周内</SelectItem>
                  <SelectItem value="m">一月内</SelectItem>
                  <SelectItem value="y">一年内</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="search-region">地区</Label>
              <Select
                value={settings.search_region}
                onValueChange={(value) => updateSetting("search_region", value)}
              >
                <SelectTrigger id="search-region">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="cn-zh">中国（简体中文）</SelectItem>
                  <SelectItem value="us-en">美国（英语）</SelectItem>
                  <SelectItem value="jp-jp">日本（日语）</SelectItem>
                  <SelectItem value="kr-kr">韩国（韩语）</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 爬虫设置 */}
      <Card>
        <CardHeader>
          <CardTitle>爬虫设置</CardTitle>
          <CardDescription>配置网页爬取的并发和超时参数</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            <div className="space-y-2">
              <Label htmlFor="concurrent">并发数</Label>
              <Input
                id="concurrent"
                type="number"
                min={1}
                max={10}
                value={settings.crawl_concurrent}
                onChange={(e) => updateSetting("crawl_concurrent", parseInt(e.target.value) || 3)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="delay">请求延迟（秒）</Label>
              <Input
                id="delay"
                type="number"
                min={0}
                max={10}
                value={settings.crawl_delay}
                onChange={(e) => updateSetting("crawl_delay", parseInt(e.target.value) || 1)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="timeout">超时时间（秒）</Label>
              <Input
                id="timeout"
                type="number"
                min={5}
                max={120}
                value={settings.crawl_timeout}
                onChange={(e) => updateSetting("crawl_timeout", parseInt(e.target.value) || 30)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="retry">重试次数</Label>
              <Input
                id="retry"
                type="number"
                min={0}
                max={5}
                value={settings.crawl_retry_count}
                onChange={(e) => updateSetting("crawl_retry_count", parseInt(e.target.value) || 2)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Sitemap 设置 */}
      <Card>
        <CardHeader>
          <CardTitle>Sitemap 设置</CardTitle>
          <CardDescription>配置 Sitemap 解析选项</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>递归解析</Label>
              <p className="text-sm text-muted-foreground">解析 Sitemap 索引中的子 Sitemap</p>
            </div>
            <Switch
              checked={settings.sitemap_recursive}
              onCheckedChange={(checked) => updateSetting("sitemap_recursive", checked)}
            />
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>跟踪备选链接</Label>
              <p className="text-sm text-muted-foreground">处理 hreflang 链接以获取多语言版本</p>
            </div>
            <Switch
              checked={settings.sitemap_follow_alternates}
              onCheckedChange={(checked) => updateSetting("sitemap_follow_alternates", checked)}
            />
          </div>
        </CardContent>
      </Card>

      {/* 文章过滤设置 */}
      <Card>
        <CardHeader>
          <CardTitle>文章过滤</CardTitle>
          <CardDescription>设置文章长度的最小和最大值</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="min-length">最小长度（字符数）</Label>
              <Input
                id="min-length"
                type="number"
                min={0}
                value={settings.min_article_length}
                onChange={(e) => updateSetting("min_article_length", parseInt(e.target.value) || 50)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="max-length">最大长度（字符数）</Label>
              <Input
                id="max-length"
                type="number"
                min={100}
                value={settings.max_article_length}
                onChange={(e) => updateSetting("max_article_length", parseInt(e.target.value) || 50000)}
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
