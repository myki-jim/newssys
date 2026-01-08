import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Search, ExternalLink } from "lucide-react"

interface GoogleSearchForm {
  keywords: string
  exactPhrase: string
  anyOfThese: string
  noneOfThese: string
  site: string
  fileType: string
  language: string
  timeRange: string
}

const defaultForm: GoogleSearchForm = {
  keywords: "",
  exactPhrase: "",
  anyOfThese: "",
  noneOfThese: "",
  site: "",
  fileType: "any",
  language: "lang_zh-CN",
  timeRange: "any",
}

const presets = [
  { name: "中文搜索", description: "搜索中文内容", keywords: "人工智能", language: "lang_zh-CN", fileType: "any", timeRange: "any" },
  { name: "PDF 文档", description: "查找 PDF 文件", keywords: "research", fileType: "pdf", timeRange: "any" },
  { name: "特定网站", description: "在指定网站搜索", keywords: "AI", site: "wikipedia.org", fileType: "any", timeRange: "any" },
]

export default function GoogleSearchPage() {
  const [form, setForm] = useState<GoogleSearchForm>(defaultForm)

  const updateField = (key: keyof GoogleSearchForm, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const buildQuery = (): string => {
    const parts: string[] = []

    if (form.keywords) parts.push(form.keywords)
    if (form.exactPhrase) parts.push(`"${form.exactPhrase}"`)
    if (form.anyOfThese) {
      const words = form.anyOfThese.split(/\s+/).filter(Boolean)
      if (words.length) parts.push(`(${words.join(" OR ")})`)
    }
    if (form.noneOfThese) {
      const words = form.noneOfThese.split(/\s+/).filter(Boolean)
      words.forEach((w) => parts.push(`-${w}`))
    }
    if (form.site) parts.push(`site:${form.site}`)
    if (form.fileType && form.fileType !== "any") parts.push(`filetype:${form.fileType}`)

    return parts.join(" ")
  }

  const buildUrl = (): string => {
    const baseUrl = "https://www.google.com/search"
    const params = new URLSearchParams()

    const query = buildQuery()
    params.set("q", query)

    if (form.language) params.set("lr", form.language)

    if (form.timeRange && form.timeRange !== "any") {
      const timeMap: Record<string, string> = {
        d: "d",
        w: "w",
        m: "m",
        y: "y",
      }
      if (timeMap[form.timeRange]) {
        params.set("tbs", `qdr:${timeMap[form.timeRange]}`)
      }
    }

    return `${baseUrl}?${params.toString()}`
  }

  const handleSearch = () => {
    const query = buildQuery()
    if (!query.trim()) {
      alert("请输入至少一个搜索条件")
      return
    }
    window.open(buildUrl(), "_blank")
  }

  const applyPreset = (preset: typeof presets[0]) => {
    setForm({
      ...defaultForm,
      keywords: preset.keywords,
      language: preset.language,
      fileType: preset.fileType,
      site: preset.site || "",
    })
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Google 高级搜索</h1>
        <p className="text-muted-foreground">构建复杂搜索查询</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>搜索预设</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {presets.map((preset) => (
              <Button
                key={preset.name}
                variant="outline"
                className="h-auto flex-col items-start p-4"
                onClick={() => applyPreset(preset)}
              >
                <span className="font-medium">{preset.name}</span>
                <span className="text-xs text-muted-foreground mt-1">{preset.description}</span>
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>搜索条件</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>关键词</Label>
              <Input
                value={form.keywords}
                onChange={(e) => updateField("keywords", e.target.value)}
                placeholder="例如: 人工智能"
              />
            </div>
            <div className="space-y-2">
              <Label>精确短语</Label>
              <Input
                value={form.exactPhrase}
                onChange={(e) => updateField("exactPhrase", e.target.value)}
                placeholder='例如: "深度学习"'
              />
            </div>
            <div className="space-y-2">
              <Label>任意词 (OR)</Label>
              <Input
                value={form.anyOfThese}
                onChange={(e) => updateField("anyOfThese", e.target.value)}
                placeholder="例如: GPT Claude"
              />
            </div>
            <div className="space-y-2">
              <Label>排除词</Label>
              <Input
                value={form.noneOfThese}
                onChange={(e) => updateField("noneOfThese", e.target.value)}
                placeholder="例如: 广告"
              />
            </div>
          </div>

          <Separator />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label>网站</Label>
              <Input
                value={form.site}
                onChange={(e) => updateField("site", e.target.value)}
                placeholder="例如: wikipedia.org"
              />
            </div>
            <div className="space-y-2">
              <Label>文件类型</Label>
              <Select value={form.fileType} onValueChange={(v) => updateField("fileType", v)}>
                <SelectTrigger>
                  <SelectValue placeholder="任意类型" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="any">任意类型</SelectItem>
                  <SelectItem value="pdf">PDF</SelectItem>
                  <SelectItem value="doc">Word</SelectItem>
                  <SelectItem value="xls">Excel</SelectItem>
                  <SelectItem value="ppt">PowerPoint</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>时间范围</Label>
              <Select value={form.timeRange} onValueChange={(v) => updateField("timeRange", v)}>
                <SelectTrigger>
                  <SelectValue placeholder="任意时间" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="any">任意时间</SelectItem>
                  <SelectItem value="d">24小时内</SelectItem>
                  <SelectItem value="w">1周内</SelectItem>
                  <SelectItem value="m">1月内</SelectItem>
                  <SelectItem value="y">1年内</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label>生成的查询</Label>
            <div className="p-3 bg-muted rounded-md text-sm font-mono">
              {buildQuery() || "(等待输入...)"}
            </div>
          </div>

          <div className="flex justify-end">
            <Button size="lg" onClick={handleSearch}>
              <Search className="mr-2 h-5 w-5" />
              在 Google 搜索
              <ExternalLink className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
