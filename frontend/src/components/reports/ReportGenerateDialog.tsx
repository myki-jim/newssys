import { useState, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Loader2,
  Sparkles,
  CheckCircle,
  AlertCircle,
  Calendar,
  FileText,
  Settings,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useTimeRangePresets, useReportTemplates, useReportGenerate } from "@/hooks/useReports"
import type { ReportCreateRequest, ReportAgentStage } from "@/types"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeRaw from "rehype-raw"
import rehypeSanitize from "rehype-sanitize"

interface ReportGenerateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const STAGE_LABELS: Record<ReportAgentStage, string> = {
  initializing: "初始化中",
  filtering_articles: "筛选文章",
  generating_keywords: "AI生成关键字",
  clustering_articles: "聚类文章",
  extracting_events: "提取重点事件",
  generating_sections: "生成报告板块",
  merging_report: "合并报告",
  completed: "已完成",
}

export function ReportGenerateDialog({ open, onOpenChange }: ReportGenerateDialogProps) {
  // 表单状态
  const [title, setTitle] = useState("")
  const [templateId, setTemplateId] = useState<number | null>(null)
  const [customPrompt, setCustomPrompt] = useState("")
  const [language, setLanguage] = useState<"zh" | "kk">("zh")
  const [maxEvents, setMaxEvents] = useState(20)

  // 时间范围选择
  const [usePreset, setUsePreset] = useState(true)
  const [selectedPreset, setSelectedPreset] = useState<string>("本周")
  const [customStart, setCustomStart] = useState("")
  const [customEnd, setCustomEnd] = useState("")

  // 获取时间预设和模板
  const { data: timePresets } = useTimeRangePresets()
  const { data: templates } = useReportTemplates()
  const { state, generate, reset, isGenerating } = useReportGenerate()

  // 重置表单
  const resetForm = () => {
    setTitle("")
    setTemplateId(null)
    setCustomPrompt("")
    setLanguage("zh")
    setMaxEvents(20)
    setUsePreset(true)
    setSelectedPreset("本周")
    setCustomStart("")
    setCustomEnd("")
    reset()
  }

  const handleClose = () => {
    // 不再中断生成任务，让它继续在后台运行
    // 用户可以在详情页查看实时进度
    onOpenChange(false)
    // 只有在非生成状态或用户明确想要重置时才重置表单
    if (!isGenerating) {
      resetForm()
    }
  }

  const handleGenerate = () => {
    if (!title) return

    let timeRangeStart: string
    let timeRangeEnd: string

    if (usePreset && timePresets && selectedPreset in timePresets) {
      timeRangeStart = timePresets[selectedPreset].start
      timeRangeEnd = timePresets[selectedPreset].end
    } else {
      if (!customStart || !customEnd) return
      timeRangeStart = new Date(customStart).toISOString()
      timeRangeEnd = new Date(customEnd).toISOString()
    }

    const request: ReportCreateRequest = {
      title,
      time_range_start: timeRangeStart,
      time_range_end: timeRangeEnd,
      template_id: templateId,
      custom_prompt: customPrompt || undefined,
      max_events: maxEvents,
      language,
    }

    generate(request)
  }

  // 当模板列表加载时，设置默认模板
  useEffect(() => {
    if (templates && templates.length > 0 && !templateId) {
      const defaultTemplate = templates.find((t) => t.is_default)
      if (defaultTemplate) {
        setTemplateId(defaultTemplate.id)
      }
    }
  }, [templates, templateId])

  // 预设时间范围选项
  const presetOptions = timePresets ? Object.keys(timePresets) : []

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>生成新报告</DialogTitle>
          <DialogDescription>
            配置报告参数，AI Agent 将自动聚类文章、提取重点事件并生成结构化报告
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {isGenerating || state.status === "completed" || state.status === "error" ? (
            // 生成进度显示
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                {isGenerating ? (
                  <Loader2 className="h-5 w-5 animate-spin text-primary" />
                ) : state.status === "completed" ? (
                  <CheckCircle className="h-5 w-5 text-green-500" />
                ) : (
                  <AlertCircle className="h-5 w-5 text-destructive" />
                )}
                <span className="font-medium">{state.message || "生成中..."}</span>
              </div>

              {/* 进度条 */}
              {isGenerating && (
                <div className="space-y-2">
                  <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary transition-all duration-300"
                      style={{ width: `${state.progress}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{STAGE_LABELS[state.stage as ReportAgentStage] || state.stage}</span>
                    <span>{state.progress}%</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    报告在后台生成中，您可以关闭此窗口，稍后在报告列表查看进度
                  </p>
                </div>
              )}

              {/* 统计信息 */}
              {(state.totalArticles > 0 || state.clusteredArticles > 0 || state.eventCount > 0) && (
                <div className="grid grid-cols-3 gap-4">
                  <Card>
                    <CardContent className="pt-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold">{state.totalArticles}</div>
                        <div className="text-xs text-muted-foreground">总文章数</div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold">{state.clusteredArticles}</div>
                        <div className="text-xs text-muted-foreground">去重后</div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="pt-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold">{state.eventCount}</div>
                        <div className="text-xs text-muted-foreground">重点事件</div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}

              {/* AI 生成的关键字 */}
              {state.keywords.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Sparkles className="h-4 w-4" />
                      AI 生成的关键字
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-2">
                      {state.keywords.map((keyword, index) => (
                        <span
                          key={index}
                          className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-primary/10 text-primary border border-primary/20"
                        >
                          {keyword}
                        </span>
                      ))}
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">
                      系统根据报告标题和您的要求生成了 {state.keywords.length} 个关键字，用于筛选相关文章
                    </p>
                  </CardContent>
                </Card>
              )}

              {/* 重点事件列表 */}
              {state.events.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Sparkles className="h-4 w-4" />
                      重点事件列表
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {state.events.map((event, index) => (
                        <div
                          key={index}
                          className="p-3 rounded-md bg-muted/50 space-y-1"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <span className="text-sm font-medium flex-1">
                              {index + 1}. {event.title}
                            </span>
                            <span className="text-xs text-muted-foreground whitespace-nowrap">
                              {typeof event.importance === 'number' && !isNaN(event.importance)
                                ? `重要性: ${(event.importance * 100).toFixed(0)}%`
                                : ''}
                            </span>
                          </div>
                          <p className="text-xs text-muted-foreground line-clamp-2">
                            {event.summary}
                          </p>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* 板块预览 */}
              {state.sections.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <FileText className="h-4 w-4" />
                      报告板块
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {state.sections.map((section, index) => (
                        <div
                          key={index}
                          className="flex items-center justify-between p-2 rounded-md bg-muted/50"
                        >
                          <span className="text-sm font-medium">{section.title}</span>
                          <span className="text-xs text-muted-foreground">
                            {section.event_count} 个事件
                          </span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* AI 实时生成内容 */}
              {state.currentStreamingSection && (
                <Card className="border-primary/50">
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Sparkles className="h-4 w-4 animate-pulse text-primary" />
                      正在生成：{state.currentStreamingSection.title}
                      <Loader2 className="h-3 w-3 animate-spin text-primary ml-auto" />
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="max-h-96 overflow-y-auto rounded-md bg-muted/30 p-4">
                      <div className="prose-markdown prose-sm dark:prose-invert">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          rehypePlugins={[rehypeRaw, rehypeSanitize]}
                        >
                          {state.currentStreamingSection.content}
                        </ReactMarkdown>
                      </div>
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">
                      AI 正在实时生成内容，您可以看到完整的写作过程
                    </p>
                  </CardContent>
                </Card>
              )}

              {/* 完成 */}
              {state.status === "completed" && (
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={handleClose}>
                    关闭
                  </Button>
                  <Button onClick={handleClose}>
                    查看报告
                  </Button>
                </div>
              )}

              {/* 错误 */}
              {state.status === "error" && (
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={handleClose}>
                    关闭
                  </Button>
                  <Button onClick={handleGenerate}>重试</Button>
                </div>
              )}
            </div>
          ) : (
            // 配置表单
            <div className="space-y-4">
              {/* 报告标题 */}
              <div className="space-y-2">
                <Label htmlFor="title">
                  报告标题 <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="title"
                  placeholder="例如：本周科技行业动态分析"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>

              {/* 时间范围 */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Calendar className="h-4 w-4" />
                    时间范围
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-center gap-4">
                    <label className="flex items-center gap-2 text-sm cursor-pointer">
                      <input
                        type="radio"
                        checked={usePreset}
                        onChange={() => setUsePreset(true)}
                        className="h-4 w-4"
                      />
                      使用预设
                    </label>
                    <label className="flex items-center gap-2 text-sm cursor-pointer">
                      <input
                        type="radio"
                        checked={!usePreset}
                        onChange={() => setUsePreset(false)}
                        className="h-4 w-4"
                      />
                      自定义
                    </label>
                  </div>

                  {usePreset ? (
                    <Select value={selectedPreset} onValueChange={setSelectedPreset}>
                      <SelectTrigger>
                        <SelectValue placeholder="选择时间预设" />
                      </SelectTrigger>
                      <SelectContent>
                        {presetOptions.map((name) => (
                          <SelectItem key={name} value={name}>
                            {name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-xs">开始时间</Label>
                        <Input
                          type="datetime-local"
                          value={customStart}
                          onChange={(e) => setCustomStart(e.target.value)}
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">结束时间</Label>
                        <Input
                          type="datetime-local"
                          value={customEnd}
                          onChange={(e) => setCustomEnd(e.target.value)}
                        />
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* 模板和语言 */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="template">报告模板</Label>
                  <Select
                    value={templateId?.toString() || ""}
                    onValueChange={(v) => setTemplateId(v ? parseInt(v) : null)}
                  >
                    <SelectTrigger id="template">
                      <SelectValue placeholder="默认模板" />
                    </SelectTrigger>
                    <SelectContent>
                      {templates?.map((template) => (
                        <SelectItem key={template.id} value={template.id.toString()}>
                          {template.name} {template.is_default && "(默认)"}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="language">报告语言</Label>
                  <Select value={language} onValueChange={(v: "zh" | "kk") => setLanguage(v)}>
                    <SelectTrigger id="language">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="zh">中文</SelectItem>
                      <SelectItem value="kk">哈萨克语</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* 高级设置 */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Settings className="h-4 w-4" />
                    高级设置
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="space-y-1">
                    <Label htmlFor="maxEvents">最大事件数量</Label>
                    <Input
                      id="maxEvents"
                      type="number"
                      min={5}
                      max={50}
                      value={maxEvents}
                      onChange={(e) => setMaxEvents(parseInt(e.target.value) || 20)}
                      className="text-sm"
                    />
                    <p className="text-xs text-muted-foreground">
                      从聚类文章中提取的重点事件数量
                    </p>
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor="customPrompt">自定义要求</Label>
                    <Textarea
                      id="customPrompt"
                      placeholder="可选：添加对报告的特殊要求..."
                      value={customPrompt}
                      onChange={(e) => setCustomPrompt(e.target.value)}
                      rows={3}
                      className="text-sm resize-none"
                    />
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>

        {!isGenerating && state.status !== "completed" && state.status !== "error" && (
          <DialogFooter>
            <Button variant="outline" onClick={handleClose}>
              取消
            </Button>
            <Button onClick={handleGenerate} disabled={!title}>
              <Sparkles className="mr-2 h-4 w-4" />
              开始生成
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  )
}
