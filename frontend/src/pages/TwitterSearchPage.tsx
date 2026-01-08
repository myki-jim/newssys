import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Search, ExternalLink } from "lucide-react"

interface TwitterSearchForm {
  // 关键词
  keywords: string
  exactPhrase: string
  anyOfThese: string
  noneOfThese: string
  hashtags: string

  // 用户
  fromUser: string
  toUser: string
  mentioning: string

  // 日期
  since: string
  until: string

  // 语言
  language: string

  // 互动
  minReplies: string
  minLikes: string
  minRetweets: string

  // 过滤器
  filter: "all" | "verified" | "media" | "links" | "replies"
}

const defaultForm: TwitterSearchForm = {
  keywords: "",
  exactPhrase: "",
  anyOfThese: "",
  noneOfThese: "",
  hashtags: "",
  fromUser: "",
  toUser: "",
  mentioning: "",
  since: "",
  until: "",
  language: "zh",
  minReplies: "",
  minLikes: "",
  minRetweets: "",
  filter: "all",
}

// 预设模板
const presets = [
  {
    name: "新闻关键词搜索",
    description: "搜索包含特定关键词的推文",
    form: {
      ...defaultForm,
      keywords: "人工智能",
      language: "zh",
    },
  },
  {
    name: "特定用户推文",
    description: "搜索某个用户发布的所有推文",
    form: {
      ...defaultForm,
      fromUser: "elonmusk",
    },
  },
  {
    name: "热门话题",
    description: "搜索包含指定标签的热门推文",
    form: {
      ...defaultForm,
      hashtags: "#AI",
      minLikes: "100",
      language: "zh",
    },
  },
  {
    name: "近期讨论",
    description: "最近7天内包含关键词的讨论",
    form: {
      ...defaultForm,
      keywords: "ChatGPT",
      language: "zh",
      minReplies: "5",
    },
  },
  {
    name: "带图推文",
    description: "包含图片的推文",
    form: {
      ...defaultForm,
      keywords: "",
      filter: "media",
      language: "zh",
    },
  },
  {
    name: "认证用户发布",
    description: "仅显示已认证用户的推文",
    form: {
      ...defaultForm,
      filter: "verified",
      keywords: "科技",
      language: "zh",
    },
  },
]

export default function TwitterSearchPage() {
  const [form, setForm] = useState<TwitterSearchForm>(defaultForm)

  const updateField = <K extends keyof TwitterSearchForm>(key: K, value: TwitterSearchForm[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const buildQuery = (): string => {
    const parts: string[] = []

    // 关键词
    if (form.keywords) {
      parts.push(form.keywords)
    }

    // 精确短语
    if (form.exactPhrase) {
      parts.push(`"${form.exactPhrase}"`)
    }

    // 任意词
    if (form.anyOfThese) {
      const words = form.anyOfThese.split(/\s+/).filter(Boolean)
      if (words.length > 0) {
        parts.push(`(${words.map((w) => `${w}`).join(" OR ")})`)
      }
    }

    // 排除词
    if (form.noneOfThese) {
      const words = form.noneOfThese.split(/\s+/).filter(Boolean)
      words.forEach((word) => {
        parts.push(`-${word}`)
      })
    }

    // 标签
    if (form.hashtags) {
      const tags = form.hashtags.split(/[\s,]+/).filter(Boolean)
      tags.forEach((tag) => {
        const cleanTag = tag.startsWith("#") ? tag : `#${tag}`
        parts.push(cleanTag)
      })
    }

    // 来自用户
    if (form.fromUser) {
      parts.push(`from:${form.fromUser.replace("@", "")}`)
    }

    // 发送给用户
    if (form.toUser) {
      parts.push(`to:${form.toUser.replace("@", "")}`)
    }

    // 提及用户
    if (form.mentioning) {
      parts.push(`@${form.mentioning.replace("@", "")}`)
    }

    // 日期范围
    if (form.since) {
      parts.push(`since:${form.since}`)
    }
    if (form.until) {
      parts.push(`until:${form.until}`)
    }

    // 语言
    if (form.language && form.language !== "all") {
      parts.push(`lang:${form.language}`)
    }

    // 最小互动
    if (form.minReplies) {
      parts.push(`min_replies:${form.minReplies}`)
    }
    if (form.minLikes) {
      parts.push(`min_faves:${form.minLikes}`)
    }
    if (form.minRetweets) {
      parts.push(`min_retweets:${form.minRetweets}`)
    }

    // 过滤器
    switch (form.filter) {
      case "verified":
        parts.push("filter:verified")
        break
      case "media":
        parts.push("filter:images")
        break
      case "links":
        parts.push("filter:links")
        break
      case "replies":
        parts.push("filter:replies")
        break
    }

    return parts.join(" ")
  }

  const handleSearch = () => {
    const query = buildQuery()
    if (!query.trim()) {
      alert("请输入至少一个搜索条件")
      return
    }
    const encodedQuery = encodeURIComponent(query)
    window.open(`https://twitter.com/search?q=${encodedQuery}`, "_blank")
  }

  const applyPreset = (preset: (typeof presets)[0]) => {
    setForm(preset.form)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Twitter 高级搜索</h1>
        <p className="text-muted-foreground">构建复杂搜索查询，在 Twitter/X 上查找精准内容</p>
      </div>

      {/* 预设模板 */}
      <Card>
        <CardHeader>
          <CardTitle>搜索预设</CardTitle>
          <CardDescription>点击快速应用预设模板</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
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

      {/* 搜索表单 */}
      <Card>
        <CardHeader>
          <CardTitle>搜索条件</CardTitle>
          <CardDescription>填写以下字段构建高级搜索查询</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* 关键词 */}
          <div className="space-y-4">
            <h3 className="font-medium">关键词</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="keywords">关键词</Label>
                <Input
                  id="keywords"
                  placeholder="例如: 人工智能 AI"
                  value={form.keywords}
                  onChange={(e) => updateField("keywords", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="exactPhrase">精确短语</Label>
                <Input
                  id="exactPhrase"
                  placeholder='例如: "机器学习"'
                  value={form.exactPhrase}
                  onChange={(e) => updateField("exactPhrase", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="anyOfThese">任意词 (OR)</Label>
                <Input
                  id="anyOfThese"
                  placeholder="例如: GPT Claude Gemini"
                  value={form.anyOfThese}
                  onChange={(e) => updateField("anyOfThese", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="noneOfThese">排除词</Label>
                <Input
                  id="noneOfThese"
                  placeholder="例如: 广告 营销"
                  value={form.noneOfThese}
                  onChange={(e) => updateField("noneOfThese", e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="hashtags">标签</Label>
              <Input
                id="hashtags"
                placeholder="例如: #AI #科技"
                value={form.hashtags}
                onChange={(e) => updateField("hashtags", e.target.value)}
              />
            </div>
          </div>

          <Separator />

          {/* 用户 */}
          <div className="space-y-4">
            <h3 className="font-medium">用户</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="fromUser">来自用户</Label>
                <Input
                  id="fromUser"
                  placeholder="例如: elonmusk"
                  value={form.fromUser}
                  onChange={(e) => updateField("fromUser", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="toUser">发送给用户</Label>
                <Input
                  id="toUser"
                  placeholder="例如: elonmusk"
                  value={form.toUser}
                  onChange={(e) => updateField("toUser", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="mentioning">提及用户</Label>
                <Input
                  id="mentioning"
                  placeholder="例如: elonmusk"
                  value={form.mentioning}
                  onChange={(e) => updateField("mentioning", e.target.value)}
                />
              </div>
            </div>
          </div>

          <Separator />

          {/* 日期 */}
          <div className="space-y-4">
            <h3 className="font-medium">时间范围</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="since">起始日期</Label>
                <Input
                  id="since"
                  type="date"
                  value={form.since}
                  onChange={(e) => updateField("since", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="until">结束日期</Label>
                <Input
                  id="until"
                  type="date"
                  value={form.until}
                  onChange={(e) => updateField("until", e.target.value)}
                />
              </div>
            </div>
          </div>

          <Separator />

          {/* 互动和过滤 */}
          <div className="space-y-4">
            <h3 className="font-medium">互动与过滤</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label htmlFor="language">语言</Label>
                <Select value={form.language} onValueChange={(value) => updateField("language", value)}>
                  <SelectTrigger id="language">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">全部</SelectItem>
                    <SelectItem value="zh">中文</SelectItem>
                    <SelectItem value="en">英语</SelectItem>
                    <SelectItem value="ja">日语</SelectItem>
                    <SelectItem value="ko">韩语</SelectItem>
                    <SelectItem value="es">西班牙语</SelectItem>
                    <SelectItem value="fr">法语</SelectItem>
                    <SelectItem value="de">德语</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="minReplies">最少回复</Label>
                <Input
                  id="minReplies"
                  type="number"
                  min="0"
                  placeholder="例如: 10"
                  value={form.minReplies}
                  onChange={(e) => updateField("minReplies", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="minLikes">最少点赞</Label>
                <Input
                  id="minLikes"
                  type="number"
                  min="0"
                  placeholder="例如: 100"
                  value={form.minLikes}
                  onChange={(e) => updateField("minLikes", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="minRetweets">最少转发</Label>
                <Input
                  id="minRetweets"
                  type="number"
                  min="0"
                  placeholder="例如: 50"
                  value={form.minRetweets}
                  onChange={(e) => updateField("minRetweets", e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="filter">结果过滤</Label>
              <Select value={form.filter} onValueChange={(value: any) => updateField("filter", value)}>
                <SelectTrigger id="filter">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部结果</SelectItem>
                  <SelectItem value="verified">仅认证用户</SelectItem>
                  <SelectItem value="media">包含图片/视频</SelectItem>
                  <SelectItem value="links">包含链接</SelectItem>
                  <SelectItem value="replies">仅回复</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* 查询预览 */}
          <div className="space-y-2">
            <Label>生成的查询</Label>
            <div className="p-3 bg-muted rounded-md text-sm font-mono break-all">
              {buildQuery() || "(等待输入...)"}
            </div>
          </div>

          {/* 搜索按钮 */}
          <div className="flex justify-end">
            <Button size="lg" onClick={handleSearch}>
              <Search className="mr-2 h-5 w-5" />
              在 Twitter 上搜索
              <ExternalLink className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
