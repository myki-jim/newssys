import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import { Search, ExternalLink } from "lucide-react"

type Platform = "reddit" | "youtube"

interface RedditForm {
  keywords: string
  subreddit: string
  sort: string
  time: string
}

interface YouTubeForm {
  keywords: string
  channel: string
  duration: string
  uploadDate: string
}

const defaultRedditForm: RedditForm = {
  keywords: "",
  subreddit: "",
  sort: "relevance",
  time: "any",
}

const defaultYouTubeForm: YouTubeForm = {
  keywords: "",
  channel: "",
  duration: "any",
  uploadDate: "any",
}

const redditPresets = [
  { name: "热门讨论", keywords: "AI", subreddit: "technology", sort: "hot" },
  { name: "本周最佳", keywords: "", subreddit: "all", sort: "top", time: "week" },
]

const youtubePresets = [
  { name: "高清教程", keywords: "programming", duration: "medium", uploadDate: "year" },
  { name: "频道搜索", keywords: "AI", channel: "TED" },
]

export default function SocialMediaSearchPage() {
  const [platform, setPlatform] = useState<Platform>("reddit")
  const [redditForm, setRedditForm] = useState<RedditForm>(defaultRedditForm)
  const [youtubeForm, setYouTubeForm] = useState<YouTubeForm>(defaultYouTubeForm)

  const buildRedditQuery = (): string => {
    const parts: string[] = []
    if (redditForm.keywords) parts.push(redditForm.keywords)
    return parts.join(" ")
  }

  const buildRedditUrl = (): string => {
    const params = new URLSearchParams()
    params.set("q", buildRedditQuery())
    params.set("sort", redditForm.sort)
    if (redditForm.time !== "any") params.set("t", redditForm.time)

    if (redditForm.subreddit) {
      return `https://www.reddit.com/r/${redditForm.subreddit}/search?${params.toString()}`
    }
    return `https://www.reddit.com/search?${params.toString()}`
  }

  const buildYouTubeQuery = (): string => {
    return youtubeForm.keywords
  }

  const buildYouTubeUrl = (): string => {
    const params = new URLSearchParams()
    params.set("search_query", buildYouTubeQuery())
    return `https://www.youtube.com/results?${params.toString()}`
  }

  const handleSearch = () => {
    if (platform === "reddit") {
      window.open(buildRedditUrl(), "_blank")
    } else {
      window.open(buildYouTubeUrl(), "_blank")
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">社交媒体高级搜索</h1>
        <p className="text-muted-foreground">在 Reddit、YouTube 等平台搜索</p>
      </div>

      <Tabs value={platform} onValueChange={(v) => setPlatform(v as Platform)}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="reddit">Reddit</TabsTrigger>
          <TabsTrigger value="youtube">YouTube</TabsTrigger>
        </TabsList>

        <TabsContent value="reddit" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>搜索预设</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {redditPresets.map((preset) => (
                  <Button
                    key={preset.name}
                    variant="outline"
                    className="h-auto flex-col items-start p-4"
                    onClick={() => setRedditForm({ ...defaultRedditForm, ...preset })}
                  >
                    <span className="font-medium">{preset.name}</span>
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Reddit 搜索</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>关键词</Label>
                  <Input
                    value={redditForm.keywords}
                    onChange={(e) => setRedditForm({ ...redditForm, keywords: e.target.value })}
                    placeholder="例如: AI"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Subreddit</Label>
                  <Input
                    value={redditForm.subreddit}
                    onChange={(e) => setRedditForm({ ...redditForm, subreddit: e.target.value })}
                    placeholder="例如: technology"
                  />
                </div>
                <div className="space-y-2">
                  <Label>排序</Label>
                  <Select
                    value={redditForm.sort}
                    onValueChange={(v) => setRedditForm({ ...redditForm, sort: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="relevance">相关性</SelectItem>
                      <SelectItem value="hot">热门</SelectItem>
                      <SelectItem value="top">最高赞</SelectItem>
                      <SelectItem value="new">最新</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="p-3 bg-muted rounded-md text-sm font-mono">
                {buildRedditQuery() || "(等待输入...)"}
              </div>

              <div className="flex justify-end">
                <Button size="lg" onClick={handleSearch}>
                  <Search className="mr-2 h-5 w-5" />
                  在 Reddit 搜索
                  <ExternalLink className="ml-2 h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="youtube" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>搜索预设</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {youtubePresets.map((preset) => (
                  <Button
                    key={preset.name}
                    variant="outline"
                    className="h-auto flex-col items-start p-4"
                    onClick={() => setYouTubeForm({ ...defaultYouTubeForm, ...preset })}
                  >
                    <span className="font-medium">{preset.name}</span>
                  </Button>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>YouTube 搜索</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>关键词</Label>
                  <Input
                    value={youtubeForm.keywords}
                    onChange={(e) => setYouTubeForm({ ...youtubeForm, keywords: e.target.value })}
                    placeholder="例如: programming tutorial"
                  />
                </div>
                <div className="space-y-2">
                  <Label>频道</Label>
                  <Input
                    value={youtubeForm.channel}
                    onChange={(e) => setYouTubeForm({ ...youtubeForm, channel: e.target.value })}
                    placeholder="例如: TED"
                  />
                </div>
              </div>

              <div className="p-3 bg-muted rounded-md text-sm font-mono">
                {buildYouTubeQuery() || "(等待输入...)"}
              </div>

              <div className="flex justify-end">
                <Button size="lg" onClick={handleSearch}>
                  <Search className="mr-2 h-5 w-5" />
                  在 YouTube 搜索
                  <ExternalLink className="ml-2 h-4 w-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
