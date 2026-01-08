import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Search, ExternalLink, User, Mail, Phone, AtSign } from "lucide-react"

interface OsintForm {
  username: string
  email: string
  phone: string
  fullName: string
}

interface Platform {
  id: string
  name: string
  icon: string
  urlTemplate: (value: string, type: string) => string[]
}

const platforms: Platform[] = [
  {
    id: "twitter",
    name: "X / Twitter",
    icon: "𝕏",
    urlTemplate: (value, type) => {
      if (type === "username") {
        return [`https://twitter.com/@${value}`, `https://twitter.com/search?q=${value}`]
      }
      return [`https://twitter.com/search?q=${value}`]
    },
  },
  {
    id: "instagram",
    name: "Instagram",
    icon: "📷",
    urlTemplate: (value, type) => {
      if (type === "username") {
        return [`https://www.instagram.com/${value}/`, `https://www.instagram.com/web/search/topsearch/?query=${value}`]
      }
      return [`https://www.instagram.com/web/search/topsearch/?query=${value}`]
    },
  },
  {
    id: "linkedin",
    name: "LinkedIn",
    icon: "💼",
    urlTemplate: (value, type) => {
      return [`https://www.linkedin.com/search/results/people/?keywords=${value}`]
    },
  },
  {
    id: "telegram",
    name: "Telegram",
    icon: "✈️",
    urlTemplate: (value, type) => {
      if (type === "username") {
        return [`https://t.me/${value}`, `https://web.telegram.org/k/#q=${value}`]
      }
      return [`https://web.telegram.org/k/#q=${value}`]
    },
  },
  {
    id: "facebook",
    name: "Facebook",
    icon: "👥",
    urlTemplate: (value, type) => {
      if (type === "username") {
        return [`https://www.facebook.com/${value}`, `https://www.facebook.com/search/top?q=${value}`]
      }
      return [`https://www.facebook.com/search/top?q=${value}`]
    },
  },
  {
    id: "tiktok",
    name: "TikTok",
    icon: "🎵",
    urlTemplate: (value, type) => {
      if (type === "username") {
        return [`https://www.tiktok.com/@${value}`, `https://www.tiktok.com/search?q=${value}`]
      }
      return [`https://www.tiktok.com/search?q=${value}`]
    },
  },
  {
    id: "github",
    name: "GitHub",
    icon: "🐙",
    urlTemplate: (value, type) => {
      return [`https://github.com/search?q=${value}`, `https://github.com/${value}`]
    },
  },
  {
    id: "youtube",
    name: "YouTube",
    icon: "▶️",
    urlTemplate: (value, type) => {
      if (type === "username") {
        return [`https://www.youtube.com/@${value}`, `https://www.youtube.com/results?search_query=${value}`]
      }
      return [`https://www.youtube.com/results?search_query=${value}`]
    },
  },
  {
    id: "reddit",
    name: "Reddit",
    icon: "🤖",
    urlTemplate: (value, type) => {
      if (type === "username") {
        return [`https://www.reddit.com/user/${value}`, `https://www.reddit.com/search?q=${value}`]
      }
      return [`https://www.reddit.com/search?q=${value}`]
    },
  },
  {
    id: "pinterest",
    name: "Pinterest",
    icon: "📌",
    urlTemplate: (value, type) => {
      return [`https://www.pinterest.com/search/pins/?q=${value}`]
    },
  },
  {
    id: "snapchat",
    name: "Snapchat",
    icon: "👻",
    urlTemplate: (value, type) => {
      if (type === "username") {
        return [`https://www.snapchat.com/add/${value}`, `https://story.snapchat.com/add/${value}`]
      }
      return [`https://www.snapchat.com/add/${value}`]
    },
  },
  {
    id: "threads",
    name: "Threads",
    icon: "💬",
    urlTemplate: (value, type) => {
      if (type === "username") {
        return [`https://www.threads.net/@${value}`]
      }
      return []
    },
  },
  {
    id: "medium",
    name: "Medium",
    icon: "📝",
    urlTemplate: (value, type) => {
      return [`https://medium.com/search?q=${value}`]
    },
  },
  {
    id: "discord",
    name: "Discord",
    icon: "🎮",
    urlTemplate: (value, type) => {
      if (type === "username") {
        return [`https://discord.com/users/${value}`, `https://discord.com/invite/${value}`]
      }
      return []
    },
  },
]

const defaultForm: OsintForm = {
  username: "",
  email: "",
  phone: "",
  fullName: "",
}

export default function OsintToolsPage() {
  const [form, setForm] = useState<OsintForm>(defaultForm)
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(platforms.map((p) => p.id))
  const [searchType, setSearchType] = useState<"username" | "email" | "phone" | "fullName">("username")

  const updateField = (key: keyof OsintForm, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const getActiveValue = (): { value: string; type: string } => {
    switch (searchType) {
      case "username":
        return { value: form.username, type: "username" }
      case "email":
        return { value: form.email, type: "email" }
      case "phone":
        return { value: form.phone, type: "phone" }
      case "fullName":
        return { value: form.fullName, type: "fullName" }
    }
  }

  const buildSearchUrls = (): string[] => {
    const { value, type } = getActiveValue()
    if (!value.trim()) return []

    const urls: string[] = []
    const selectedPlatformObjs = platforms.filter((p) => selectedPlatforms.includes(p.id))

    selectedPlatformObjs.forEach((platform) => {
      try {
        const platformUrls = platform.urlTemplate(value.trim(), type)
        urls.push(...platformUrls)
      } catch (e) {
        console.error(`Error building URL for ${platform.name}:`, e)
      }
    })

    return urls
  }

  const handleSearch = () => {
    const urls = buildSearchUrls()
    if (urls.length === 0) {
      alert("请输入搜索内容")
      return
    }

    // 批量打开所有标签页
    urls.forEach((url, index) => {
      setTimeout(() => {
        window.open(url, "_blank")
      }, index * 200) // 每200ms打开一个，避免被浏览器拦截
    })
  }

  const copyUrls = () => {
    const urls = buildSearchUrls()
    if (urls.length === 0) {
      alert("请输入搜索内容")
      return
    }

    const text = urls.join("\n")
    navigator.clipboard.writeText(text).then(() => {
      alert(`已复制 ${urls.length} 个链接到剪贴板`)
    })
  }

  const toggleAll = () => {
    if (selectedPlatforms.length === platforms.length) {
      setSelectedPlatforms([])
    } else {
      setSelectedPlatforms(platforms.map((p) => p.id))
    }
  }

  const { value: activeValue } = getActiveValue()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">社工工具 (OSINT)</h1>
        <p className="text-muted-foreground">通过用户名、邮箱、手机号等在社交媒体上查找信息</p>
      </div>

      {/* 搜索输入 */}
      <Card>
        <CardHeader>
          <CardTitle>输入搜索信息</CardTitle>
          <CardDescription>输入至少一项信息，系统将自动在选中的平台搜索</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="username" className="flex items-center gap-2">
                <AtSign className="h-4 w-4" />
                用户名
              </Label>
              <Input
                id="username"
                placeholder="例如: johndoe"
                value={form.username}
                onChange={(e) => {
                  updateField("username", e.target.value)
                  setSearchType("username")
                }}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email" className="flex items-center gap-2">
                <Mail className="h-4 w-4" />
                邮箱
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="例如: john@example.com"
                value={form.email}
                onChange={(e) => {
                  updateField("email", e.target.value)
                  setSearchType("email")
                }}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="phone" className="flex items-center gap-2">
                <Phone className="h-4 w-4" />
                手机号
              </Label>
              <Input
                id="phone"
                placeholder="例如: +8613800138000"
                value={form.phone}
                onChange={(e) => {
                  updateField("phone", e.target.value)
                  setSearchType("phone")
                }}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="fullName" className="flex items-center gap-2">
                <User className="h-4 w-4" />
                姓名
              </Label>
              <Input
                id="fullName"
                placeholder="例如: John Doe"
                value={form.fullName}
                onChange={(e) => {
                  updateField("fullName", e.target.value)
                  setSearchType("fullName")
                }}
              />
            </div>
          </div>

          {/* 搜索按钮 */}
          <div className="flex gap-2">
            <Button size="lg" onClick={handleSearch} disabled={!activeValue}>
              <Search className="mr-2 h-5 w-5" />
              开始搜索 ({buildSearchUrls().length} 个链接)
              <ExternalLink className="ml-2 h-4 w-4" />
            </Button>
            <Button size="lg" variant="outline" onClick={copyUrls} disabled={!activeValue}>
              复制所有链接
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 平台选择 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>选择平台</CardTitle>
              <CardDescription>
                已选择 {selectedPlatforms.length} / {platforms.length} 个平台
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={toggleAll}>
              {selectedPlatforms.length === platforms.length ? "取消全选" : "全选"}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {platforms.map((platform) => (
              <div
                key={platform.id}
                className="flex items-center space-x-2 p-3 border rounded-lg hover:bg-muted cursor-pointer"
                onClick={() => {
                  if (selectedPlatforms.includes(platform.id)) {
                    setSelectedPlatforms(selectedPlatforms.filter((id) => id !== platform.id))
                  } else {
                    setSelectedPlatforms([...selectedPlatforms, platform.id])
                  }
                }}
              >
                <Checkbox
                  checked={selectedPlatforms.includes(platform.id)}
                  onChange={() => {}}
                />
                <span className="text-xl">{platform.icon}</span>
                <span className="text-sm">{platform.name}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* 预览 */}
      {activeValue && (
        <Card>
          <CardHeader>
            <CardTitle>搜索预览</CardTitle>
            <CardDescription>将打开以下链接</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {buildSearchUrls().map((url, index) => {
                const platform = platforms.find((p) => url.includes(p.id.replace("snapchat", "snapchat").replace("threads", "threads")))
                return (
                  <div key={index} className="flex items-center justify-between p-2 bg-muted rounded text-sm">
                    <div className="flex items-center gap-2 overflow-hidden">
                      <span className="text-lg">{platform?.icon}</span>
                      <span className="truncate">{url}</span>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => window.open(url, "_blank")}
                    >
                      <ExternalLink className="h-3 w-3" />
                    </Button>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 使用提示 */}
      <Card>
        <CardHeader>
          <CardTitle>使用提示</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>• <strong>用户名搜索</strong>：最常用，直接访问用户主页和搜索结果</p>
          <p>• <strong>邮箱搜索</strong>：部分平台支持邮箱查找用户</p>
          <p>• <strong>手机号搜索</strong>：部分平台支持手机号查找（需带国家代码）</p>
          <p>• <strong>姓名搜索</strong>：在平台内搜索姓名关键词</p>
          <p className="mt-4 text-amber-600">⚠️ 注意：请仅用于合法用途，如寻找失联好友、背景调查等。禁止用于骚扰、跟踪或其他违法行为。</p>
        </CardContent>
      </Card>
    </div>
  )
}
