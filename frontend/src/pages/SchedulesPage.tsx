/**
 * 定时计划页面
 * 用于管理定时任务：Sitemap爬取、文章自动爬取、关键词搜索
 */

import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import {
  Clock,
  Play,
  Pause,
  Trash2,
  Plus,
  Edit,
  Calendar,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Settings,
  Search,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"

// 类型定义
interface Schedule {
  id: number
  name: string
  description: string | null
  schedule_type: "sitemap_crawl" | "article_crawl" | "keyword_search"
  status: "active" | "paused" | "disabled"
  interval_minutes: number
  max_executions: number | null
  execution_count: number
  config: Record<string, any> | null
  last_run_at: string | null
  next_run_at: string | null
  last_status: string | null
  last_error: string | null
  created_at: string
  updated_at: string
}

interface Keyword {
  id: number
  keyword: string
  description: string | null
  time_range: string
  max_results: number
  region: string
  is_active: boolean
  search_count: number
  last_searched_at: string | null
  created_at: string
  updated_at: string
}

export default function SchedulesPage() {
  const navigate = useNavigate()
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [keywords, setKeywords] = useState<Keyword[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState("schedules")

  // Dialog 状态
  const [showScheduleDialog, setShowScheduleDialog] = useState(false)
  const [showKeywordDialog, setShowKeywordDialog] = useState(false)
  const [editingItem, setEditingItem] = useState<Schedule | Keyword | null>(null)

  // 表单状态
  const [scheduleForm, setScheduleForm] = useState<{
    name: string
    description: string
    schedule_type: Schedule["schedule_type"]
    interval_minutes: number
    max_executions: number | null
    config: Record<string, any>
  }>({
    name: "",
    description: "",
    schedule_type: "sitemap_crawl",
    interval_minutes: 60,
    max_executions: null,
    config: {},
  })

  const [keywordForm, setKeywordForm] = useState({
    keyword: "",
    description: "",
    time_range: "w",
    max_results: 10,
    region: "us-en",
    is_active: true,
  })

  useEffect(() => {
    loadData()
  }, [activeTab])

  const loadData = async () => {
    setLoading(true)
    try {
      if (activeTab === "schedules") {
        const res = await fetch("/api/v1/schedules")
        const data = await res.json()
        if (data.success) {
          setSchedules(data.data || [])
        }
      } else {
        const res = await fetch("/api/v1/keywords")
        const data = await res.json()
        if (data.success) {
          setKeywords(data.data || [])
        }
      }
    } catch (error) {
      console.error("Failed to load data:", error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreateSchedule = async () => {
    try {
      // 计算下次运行时间
      const next_run_at = new Date(Date.now() + scheduleForm.interval_minutes * 60 * 1000).toISOString()

      const res = await fetch("/api/v1/schedules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...scheduleForm,
          next_run_at,
        }),
      })

      const data = await res.json()
      if (data.success) {
        setShowScheduleDialog(false)
        resetScheduleForm()
        loadData()
      } else {
        alert("创建失败: " + JSON.stringify(data.error))
      }
    } catch (error) {
      console.error("Failed to create schedule:", error)
      alert("创建失败")
    }
  }

  const handleUpdateSchedule = async () => {
    if (!editingItem) return

    try {
      const res = await fetch(`/api/v1/schedules/${editingItem.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(scheduleForm),
      })

      const data = await res.json()
      if (data.success) {
        setShowScheduleDialog(false)
        setEditingItem(null)
        resetScheduleForm()
        loadData()
      }
    } catch (error) {
      console.error("Failed to update schedule:", error)
    }
  }

  const handleDeleteSchedule = async (id: number) => {
    if (!confirm("确定要删除这个定时任务吗？")) return

    try {
      const res = await fetch(`/api/v1/schedules/${id}`, {
        method: "DELETE",
      })

      const data = await res.json()
      if (data.success) {
        loadData()
      }
    } catch (error) {
      console.error("Failed to delete schedule:", error)
    }
  }

  const handleExecuteSchedule = async (id: number) => {
    try {
      const res = await fetch(`/api/v1/schedules/${id}/execute`, {
        method: "POST",
      })

      const data = await res.json()
      if (data.success) {
        alert("任务已开始执行")
        loadData()
      }
    } catch (error) {
      console.error("Failed to execute schedule:", error)
    }
  }

  const handlePauseResumeSchedule = async (schedule: Schedule) => {
    const endpoint = schedule.status === "active" ? "pause" : "resume"

    try {
      const res = await fetch(`/api/v1/schedules/${schedule.id}/${endpoint}`, {
        method: "POST",
      })

      const data = await res.json()
      if (data.success) {
        loadData()
      }
    } catch (error) {
      console.error("Failed to pause/resume schedule:", error)
    }
  }

  const handleCreateKeyword = async () => {
    try {
      const res = await fetch("/api/v1/keywords", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(keywordForm),
      })

      const data = await res.json()
      if (data.success) {
        setShowKeywordDialog(false)
        resetKeywordForm()
        loadData()
      } else {
        alert("创建失败: " + JSON.stringify(data.error))
      }
    } catch (error) {
      console.error("Failed to create keyword:", error)
    }
  }

  const handleUpdateKeyword = async () => {
    if (!editingItem) return

    try {
      const res = await fetch(`/api/v1/keywords/${editingItem.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(keywordForm),
      })

      const data = await res.json()
      if (data.success) {
        setShowKeywordDialog(false)
        setEditingItem(null)
        resetKeywordForm()
        loadData()
      }
    } catch (error) {
      console.error("Failed to update keyword:", error)
    }
  }

  const handleDeleteKeyword = async (id: number) => {
    if (!confirm("确定要删除这个关键词吗？")) return

    try {
      const res = await fetch(`/api/v1/keywords/${id}`, {
        method: "DELETE",
      })

      const data = await res.json()
      if (data.success) {
        loadData()
      }
    } catch (error) {
      console.error("Failed to delete keyword:", error)
    }
  }

  const openScheduleDialog = (schedule?: Schedule) => {
    if (schedule) {
      setEditingItem(schedule)
      setScheduleForm({
        name: schedule.name,
        description: schedule.description || "",
        schedule_type: schedule.schedule_type,
        interval_minutes: schedule.interval_minutes,
        max_executions: schedule.max_executions,
        config: schedule.config || {},
      })
    } else {
      setEditingItem(null)
      resetScheduleForm()
    }
    setShowScheduleDialog(true)
  }

  const openKeywordDialog = (keyword?: Keyword) => {
    if (keyword) {
      setEditingItem(keyword)
      setKeywordForm({
        keyword: keyword.keyword,
        description: keyword.description || "",
        time_range: keyword.time_range,
        max_results: keyword.max_results,
        region: keyword.region,
        is_active: keyword.is_active,
      })
    } else {
      setEditingItem(null)
      resetKeywordForm()
    }
    setShowKeywordDialog(true)
  }

  const resetScheduleForm = () => {
    setScheduleForm({
      name: "",
      description: "",
      schedule_type: "sitemap_crawl",
      interval_minutes: 60,
      max_executions: null,
      config: {},
    })
  }

  const resetKeywordForm = () => {
    setKeywordForm({
      keyword: "",
      description: "",
      time_range: "w",
      max_results: 10,
      region: "us-en",
      is_active: true,
    })
  }

  const getScheduleTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      sitemap_crawl: "Sitemap爬取",
      article_crawl: "文章自动爬取",
      keyword_search: "关键词搜索",
    }
    return labels[type] || type
  }

  const getStatusBadge = (status: string) => {
    const variants: Record<string, "default" | "secondary" | "destructive"> = {
      active: "default",
      paused: "secondary",
      disabled: "destructive",
    }
    const labels: Record<string, string> = {
      active: "运行中",
      paused: "已暂停",
      disabled: "已禁用",
    }
    return (
      <Badge variant={variants[status] || "default"}>
        {labels[status] || status}
      </Badge>
    )
  }

  const formatDateTime = (dateStr: string | null) => {
    if (!dateStr) return "-"
    return new Date(dateStr).toLocaleString("zh-CN")
  }

  const formatInterval = (minutes: number) => {
    if (minutes < 60) return `${minutes}分钟`
    if (minutes < 1440) return `${Math.floor(minutes / 60)}小时`
    return `${Math.floor(minutes / 1440)}天`
  }

  return (
    <div className="container mx-auto py-6 max-w-7xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">定时计划</h1>
          <p className="text-muted-foreground mt-1">
            管理 Sitemap 爬取、文章自动爬取和关键词搜索的定时任务
          </p>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList>
          <TabsTrigger value="schedules" className="flex items-center gap-2">
            <Clock className="w-4 h-4" />
            定时任务
          </TabsTrigger>
          <TabsTrigger value="keywords" className="flex items-center gap-2">
            <Search className="w-4 h-4" />
            搜索关键词
          </TabsTrigger>
        </TabsList>

        {/* 定时任务标签页 */}
        <TabsContent value="schedules" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>定时任务列表</CardTitle>
                  <CardDescription>
                    管理自动执行的定时任务，支持 Sitemap 爬取、文章爬取和关键词搜索
                  </CardDescription>
                </div>
                <Button onClick={() => openScheduleDialog()}>
                  <Plus className="w-4 h-4 mr-2" />
                  新建任务
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="text-center py-8">加载中...</div>
              ) : schedules.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  暂无定时任务，点击"新建任务"创建
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>任务名称</TableHead>
                      <TableHead>类型</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead>执行间隔</TableHead>
                      <TableHead>执行次数</TableHead>
                      <TableHead>上次运行</TableHead>
                      <TableHead>下次运行</TableHead>
                      <TableHead>操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {schedules.map((schedule) => (
                      <TableRow key={schedule.id}>
                        <TableCell>
                          <div>
                            <div className="font-medium">{schedule.name}</div>
                            {schedule.description && (
                              <div className="text-sm text-muted-foreground">
                                {schedule.description}
                              </div>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>{getScheduleTypeLabel(schedule.schedule_type)}</TableCell>
                        <TableCell>{getStatusBadge(schedule.status)}</TableCell>
                        <TableCell>{formatInterval(schedule.interval_minutes)}</TableCell>
                        <TableCell>
                          {schedule.max_executions
                            ? `${schedule.execution_count}/${schedule.max_executions}`
                            : schedule.execution_count}
                        </TableCell>
                        <TableCell>{formatDateTime(schedule.last_run_at)}</TableCell>
                        <TableCell>{formatDateTime(schedule.next_run_at)}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {schedule.status === "active" ? (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handlePauseResumeSchedule(schedule)}
                              >
                                <Pause className="w-4 h-4" />
                              </Button>
                            ) : (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handlePauseResumeSchedule(schedule)}
                              >
                                <Play className="w-4 h-4" />
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleExecuteSchedule(schedule.id)}
                              disabled={schedule.status !== "active"}
                            >
                              <Settings className="w-4 h-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => openScheduleDialog(schedule)}
                            >
                              <Edit className="w-4 h-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleDeleteSchedule(schedule.id)}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 关键词标签页 */}
        <TabsContent value="keywords" className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>搜索关键词列表</CardTitle>
                  <CardDescription>
                    管理定时搜索的关键词，自动搜索并保存相关文章
                  </CardDescription>
                </div>
                <Button onClick={() => openKeywordDialog()}>
                  <Plus className="w-4 h-4 mr-2" />
                  新建关键词
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="text-center py-8">加载中...</div>
              ) : keywords.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  暂无关键词，点击"新建关键词"创建
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>关键词</TableHead>
                      <TableHead>状态</TableHead>
                      <TableHead>时间范围</TableHead>
                      <TableHead>结果数</TableHead>
                      <TableHead>搜索次数</TableHead>
                      <TableHead>上次搜索</TableHead>
                      <TableHead>操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {keywords.map((keyword) => (
                      <TableRow key={keyword.id}>
                        <TableCell>
                          <div>
                            <div className="font-medium">{keyword.keyword}</div>
                            {keyword.description && (
                              <div className="text-sm text-muted-foreground">
                                {keyword.description}
                              </div>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          {keyword.is_active ? (
                            <Badge variant="default">激活</Badge>
                          ) : (
                            <Badge variant="secondary">未激活</Badge>
                          )}
                        </TableCell>
                        <TableCell>{keyword.time_range}</TableCell>
                        <TableCell>{keyword.max_results}</TableCell>
                        <TableCell>{keyword.search_count}</TableCell>
                        <TableCell>{formatDateTime(keyword.last_searched_at)}</TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => openKeywordDialog(keyword)}
                            >
                              <Edit className="w-4 h-4" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleDeleteKeyword(keyword.id)}
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 定时任务对话框 */}
      <Dialog open={showScheduleDialog} onOpenChange={setShowScheduleDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editingItem ? "编辑定时任务" : "新建定时任务"}
            </DialogTitle>
            <DialogDescription>
              配置定时任务的执行参数和关联配置
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">任务名称 *</Label>
              <Input
                id="name"
                value={scheduleForm.name}
                onChange={(e) =>
                  setScheduleForm({ ...scheduleForm, name: e.target.value })
                }
                placeholder="例如：每日 Sitemap 爬取"
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="description">任务描述</Label>
              <Textarea
                id="description"
                value={scheduleForm.description}
                onChange={(e) =>
                  setScheduleForm({ ...scheduleForm, description: e.target.value })
                }
                placeholder="任务的详细描述..."
                rows={2}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="schedule_type">任务类型 *</Label>
                <Select
                  value={scheduleForm.schedule_type}
                  onValueChange={(value) =>
                    setScheduleForm({
                      ...scheduleForm,
                      schedule_type: value as any,
                    })
                  }
                >
                  <SelectTrigger id="schedule_type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="sitemap_crawl">Sitemap爬取</SelectItem>
                    <SelectItem value="article_crawl">文章自动爬取</SelectItem>
                    <SelectItem value="keyword_search">关键词搜索</SelectItem>
                    <SelectItem value="cleanup_low_quality">清理低质量内容</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="interval_minutes">执行间隔（分钟）*</Label>
                <Input
                  id="interval_minutes"
                  type="number"
                  value={scheduleForm.interval_minutes}
                  onChange={(e) =>
                    setScheduleForm({
                      ...scheduleForm,
                      interval_minutes: parseInt(e.target.value) || 60,
                    })
                  }
                  min={1}
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="max_executions">最大执行次数（留空表示无限）</Label>
              <Input
                id="max_executions"
                type="number"
                value={scheduleForm.max_executions || ""}
                onChange={(e) =>
                  setScheduleForm({
                    ...scheduleForm,
                    max_executions: e.target.value
                      ? parseInt(e.target.value)
                      : null,
                  })
                }
                placeholder="留空表示无限执行"
                min={1}
              />
            </div>

            {/* 根据任务类型显示不同的配置 */}
            {scheduleForm.schedule_type === "sitemap_crawl" && (
              <div className="grid gap-2">
                <Label>Sitemap ID *</Label>
                <Input
                  type="number"
                  value={scheduleForm.config?.sitemap_id || ""}
                  onChange={(e) =>
                    setScheduleForm({
                      ...scheduleForm,
                      config: {
                        ...scheduleForm.config,
                        sitemap_id: parseInt(e.target.value) || null,
                      },
                    })
                  }
                  placeholder="输入 Sitemap ID"
                />
              </div>
            )}

            {scheduleForm.schedule_type === "keyword_search" && (
              <div className="grid gap-2">
                <Label>关键词 ID *</Label>
                <Input
                  type="number"
                  value={scheduleForm.config?.keyword_id || ""}
                  onChange={(e) =>
                    setScheduleForm({
                      ...scheduleForm,
                      config: {
                        ...scheduleForm.config,
                        keyword_id: parseInt(e.target.value) || null,
                      },
                    })
                  }
                  placeholder="输入关键词 ID"
                />
              </div>
            )}

            {scheduleForm.schedule_type === "article_crawl" && (
              <div className="grid gap-2">
                <Label>批处理大小</Label>
                <Input
                  type="number"
                  value={scheduleForm.config?.batch_size || 50}
                  onChange={(e) =>
                    setScheduleForm({
                      ...scheduleForm,
                      config: {
                        ...scheduleForm.config,
                        batch_size: parseInt(e.target.value) || 50,
                      },
                    })
                  }
                  placeholder="每次爬取的文章数量"
                  min={1}
                  max={500}
                />
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowScheduleDialog(false)}
            >
              取消
            </Button>
            <Button onClick={editingItem ? handleUpdateSchedule : handleCreateSchedule}>
              {editingItem ? "更新" : "创建"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 关键词对话框 */}
      <Dialog open={showKeywordDialog} onOpenChange={setShowKeywordDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>
              {editingItem ? "编辑关键词" : "新建关键词"}
            </DialogTitle>
            <DialogDescription>
              配置自动搜索的关键词参数
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="keyword">关键词 *</Label>
              <Input
                id="keyword"
                value={keywordForm.keyword}
                onChange={(e) =>
                  setKeywordForm({ ...keywordForm, keyword: e.target.value })
                }
                placeholder="例如：哈萨克斯坦"
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="kw-description">描述</Label>
              <Textarea
                id="kw-description"
                value={keywordForm.description}
                onChange={(e) =>
                  setKeywordForm({
                    ...keywordForm,
                    description: e.target.value,
                  })
                }
                placeholder="关键词的描述..."
                rows={2}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="time_range">时间范围</Label>
                <Select
                  value={keywordForm.time_range}
                  onValueChange={(value) =>
                    setKeywordForm({ ...keywordForm, time_range: value })
                  }
                >
                  <SelectTrigger id="time_range">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="d">最近一天</SelectItem>
                    <SelectItem value="w">最近一周</SelectItem>
                    <SelectItem value="m">最近一月</SelectItem>
                    <SelectItem value="y">最近一年</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="max_results">最大结果数</Label>
                <Input
                  id="max_results"
                  type="number"
                  value={keywordForm.max_results}
                  onChange={(e) =>
                    setKeywordForm({
                      ...keywordForm,
                      max_results: parseInt(e.target.value) || 10,
                    })
                  }
                  min={1}
                  max={100}
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="region">地区</Label>
              <Select
                value={keywordForm.region}
                onValueChange={(value) =>
                  setKeywordForm({ ...keywordForm, region: value })
                }
              >
                <SelectTrigger id="region">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="us-en">美国 (英语)</SelectItem>
                  <SelectItem value="cn-zh">中国 (中文)</SelectItem>
                  <SelectItem value="kz-ru">哈萨克斯坦 (俄语)</SelectItem>
                  <SelectItem value="ru-ru">俄罗斯 (俄语)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowKeywordDialog(false)}
            >
              取消
            </Button>
            <Button onClick={editingItem ? handleUpdateKeyword : handleCreateKeyword}>
              {editingItem ? "更新" : "创建"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
