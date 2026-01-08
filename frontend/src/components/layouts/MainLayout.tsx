import { Outlet, Link, useLocation, useNavigate } from "react-router-dom"
import { cn } from "@/lib/utils"
import { useEffect, useState } from "react"
import {
  LayoutDashboard,
  Globe,
  Network,
  FileText,
  ScrollText,
  Settings,
  FileJson,
  Search,
  Menu,
  X,
  ListChecks,
  MessageSquare,
  Clock,
  Twitter,
  Youtube,
  Users,
  Fingerprint,
  LogOut,
  Shield,
} from "lucide-react"

interface User {
  id: number
  username: string
  role: string
  is_active: boolean
  office: string | null
}

interface NavigationItem {
  name: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  adminOnly?: boolean
}

const navigation: NavigationItem[] = [
  { name: "仪表盘", href: "/dashboard", icon: LayoutDashboard },
  { name: "采集源", href: "/sources", icon: Globe },
  { name: "Sitemap 管理", href: "/sitemaps", icon: Network },
  { name: "文章库", href: "/articles", icon: FileText },
  { name: "报告生成", href: "/reports", icon: ScrollText },
  { name: "模板管理", href: "/templates", icon: FileJson },
  { name: "联网搜索", href: "/search", icon: Search },
  { name: "Twitter 搜索", href: "/twitter-search", icon: Twitter },
  { name: "Google 搜索", href: "/google-search", icon: Search },
  // { name: "社交媒体搜索", href: "/social-search", icon: Users },
  // { name: "社工工具", href: "/osint", icon: Fingerprint },
  { name: "定时计划", href: "/schedules", icon: Clock },
  { name: "任务管理", href: "/tasks", icon: ListChecks },
  { name: "AI 对话", href: "/chat", icon: MessageSquare },
  { name: "系统设置", href: "/settings", icon: Settings },
  { name: "用户管理", href: "/users", icon: Shield, adminOnly: true },
]

export function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [currentUser, setCurrentUser] = useState<User | null>(null)
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    const userStr = localStorage.getItem("user")
    if (userStr) {
      try {
        setCurrentUser(JSON.parse(userStr))
      } catch (e) {
        console.error("Failed to parse user from localStorage:", e)
      }
    }
  }, [])

  const handleLogout = () => {
    localStorage.removeItem("token")
    localStorage.removeItem("user")
    navigate("/login")
  }

  // 过滤导航项：只显示非管理员专属项，或当前用户是管理员
  const filteredNavigation = navigation.filter((item) => {
    if (item.adminOnly) {
      return currentUser?.role === "admin"
    }
    return true
  })

  return (
    <div className="flex h-screen bg-background">
      {/* 侧边栏 */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 transform border-r bg-card transition-transform duration-200 ease-in-out lg:static lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-full flex-col">
          {/* Logo */}
          <div className="flex h-16 items-center border-b px-6">
            <h1 className="text-xl font-bold text-primary">新闻态势分析系统</h1>
          </div>

          {/* 导航 */}
          <nav className="flex-1 space-y-1 px-3 py-4 overflow-y-auto">
            {filteredNavigation.map((item) => {
              const isActive = location.pathname === item.href
              const Icon = item.icon

              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                  onClick={() => setSidebarOpen(false)}
                >
                  <Icon className="h-5 w-5" />
                  {item.name}
                </Link>
              )
            })}
          </nav>

          {/* 底部信息 */}
          <div className="border-t p-4">
            <div className="text-xs text-muted-foreground">
              <p>新闻态势分析系统</p>
              <p className="mt-1">v2.0.0</p>
            </div>
          </div>
        </div>
      </aside>

      {/* 遮罩层（移动端） */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* 主内容区 */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* 顶部栏 */}
        <header className="flex h-16 items-center justify-between border-b bg-card px-6">
          <button
            className="lg:hidden"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-6 w-6" />
          </button>

          <div className="flex-1" />

          <div className="flex items-center gap-4">
            {/* 状态指示器 */}
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
              </span>
              <span className="text-sm text-muted-foreground">系统正常</span>
            </div>

            {/* 用户信息 */}
            {currentUser && (
              <div className="flex items-center gap-3 border-l pl-4">
                <div className="text-right">
                  <div className="text-sm font-medium">{currentUser.username}</div>
                  <div className="text-xs text-muted-foreground">
                    {currentUser.office || "管理员"}
                  </div>
                </div>
                <button
                  onClick={handleLogout}
                  className="rounded-lg p-2 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                  title="退出登录"
                >
                  <LogOut className="h-5 w-5" />
                </button>
              </div>
            )}
          </div>
        </header>

        {/* 内容区 */}
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
