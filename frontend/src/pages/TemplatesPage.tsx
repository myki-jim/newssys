import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { reportsApi } from "@/services/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Loader2,
  Plus,
  Edit,
  Trash2,
  Star,
  StarOff,
  FileText,
} from "lucide-react"
import { formatDateTime } from "@/lib/utils"
import type { ReportTemplate, ReportTemplateCreate, SectionTemplate } from "@/types"

export function TemplatesPage() {
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<ReportTemplate | null>(null)

  // 表单状态
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [systemPrompt, setSystemPrompt] = useState("")
  const [sections, setSections] = useState<SectionTemplate[]>([])
  const [newSectionTitle, setNewSectionTitle] = useState("")
  const [newSectionDesc, setNewSectionDesc] = useState("")

  // 获取模板列表
  const { data: templates, isLoading } = useQuery({
    queryKey: ["report-templates"],
    queryFn: () => reportsApi.templates.list(100),
  })

  // 创建/更新模板
  const saveMutation = useMutation({
    mutationFn: (data: { template: ReportTemplateCreate; id?: number }) => {
      if (data.id) {
        return reportsApi.templates.update(data.id, data.template)
      }
      return reportsApi.templates.create(data.template)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["report-templates"] })
      handleCloseDialog()
    },
  })

  // 删除模板
  const deleteMutation = useMutation({
    mutationFn: (templateId: number) => reportsApi.templates.delete(templateId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["report-templates"] })
    },
  })

  // 设置默认模板
  const setDefaultMutation = useMutation({
    mutationFn: (templateId: number) => {
      // 先取消所有默认
      return Promise.all([
        ...templates!.filter(t => t.is_default).map(t => reportsApi.templates.update(t.id, { is_default: false })),
        reportsApi.templates.update(templateId, { is_default: true }),
      ])
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["report-templates"] })
    },
  })

  const handleCreate = () => {
    setEditingTemplate(null)
    setName("")
    setDescription("")
    setSystemPrompt(
      "你是一个专业的新闻分析助手，负责根据给定的新闻事件生成结构化的新闻报告。\n\n" +
      "请遵循以下规则：\n" +
      "1. 基于事件给出准确、全面的分析\n" +
      "2. 使用专业、客观的语言\n" +
      "3. 报告应结构化、易读\n" +
      "4. 使用Markdown格式"
    )
    setSections([
      { title: "重点事件", description: "本期最重要的新闻事件" },
      { title: "详细分析", description: "事件的深度分析" },
      { title: "总结", description: "本期总结" },
    ])
    setDialogOpen(true)
  }

  const handleEdit = (template: ReportTemplate) => {
    setEditingTemplate(template)
    setName(template.name)
    setDescription(template.description || "")
    setSystemPrompt(template.system_prompt)
    setSections(template.section_template)
    setDialogOpen(true)
  }

  const handleCloseDialog = () => {
    setDialogOpen(false)
    setEditingTemplate(null)
    setName("")
    setDescription("")
    setSystemPrompt("")
    setSections([])
    setNewSectionTitle("")
    setNewSectionDesc("")
  }

  const handleSave = () => {
    if (!name || !systemPrompt) return

    const template: ReportTemplateCreate = {
      name,
      description: description || undefined,
      system_prompt: systemPrompt,
      section_template: sections.length > 0 ? sections : [
        { title: "重点事件", description: "本期最重要的新闻事件" },
      ],
    }

    saveMutation.mutate({
      template,
      id: editingTemplate?.id,
    })
  }

  const handleAddSection = () => {
    if (!newSectionTitle) return
    setSections([...sections, { title: newSectionTitle, description: newSectionDesc }])
    setNewSectionTitle("")
    setNewSectionDesc("")
  }

  const handleRemoveSection = (index: number) => {
    setSections(sections.filter((_, i) => i !== index))
  }

  const handleSetDefault = (templateId: number) => {
    setDefaultMutation.mutate(templateId)
  }

  return (
    <div className="space-y-6">
      {/* 页面标题和操作 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">报告模板管理</h1>
          <p className="text-muted-foreground">
            创建和管理报告生成模板，自定义报告结构和风格
          </p>
        </div>
        <Button onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" />
          新建模板
        </Button>
      </div>

      {/* 模板列表 */}
      <Card>
        <CardHeader>
          <CardTitle>模板列表 ({templates?.length || 0})</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : templates && templates.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>名称</TableHead>
                    <TableHead>描述</TableHead>
                    <TableHead>板块数量</TableHead>
                    <TableHead>默认</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {templates.map((template) => (
                    <TableRow key={template.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-muted-foreground" />
                          <span className="font-medium">{template.name}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm text-muted-foreground">
                          {template.description || "-"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="text-xs">
                          {template.section_template?.length || 0} 个板块
                        </Badge>
                      </TableCell>
                      <TableCell>
                        {template.is_default ? (
                          <Badge variant="default" className="gap-1">
                            <Star className="h-3 w-3" />
                            默认
                          </Badge>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleSetDefault(template.id)}
                            className="h-7 text-xs"
                          >
                            <StarOff className="h-3 w-3 mr-1" />
                            设为默认
                          </Button>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {formatDateTime(template.created_at)}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleEdit(template)}
                            title="编辑"
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => deleteMutation.mutate(template.id)}
                            disabled={deleteMutation.isPending}
                            title="删除"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex h-64 flex-col items-center justify-center text-muted-foreground">
              <FileText className="h-12 w-12 mb-4 opacity-50" />
              <p>暂无模板</p>
              <Button
                variant="outline"
                className="mt-4"
                onClick={handleCreate}
              >
                创建第一个模板
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 编辑对话框 */}
      <Dialog open={dialogOpen} onOpenChange={handleCloseDialog}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingTemplate ? "编辑模板" : "新建模板"}</DialogTitle>
            <DialogDescription>
              配置报告模板，包括系统提示词和报告板块结构
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">
                  模板名称 <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="name"
                  placeholder="例如：科技行业周报"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">描述</Label>
                <Input
                  id="description"
                  placeholder="简短描述此模板的用途"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="systemPrompt">
                系统提示词 <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="systemPrompt"
                placeholder="定义 AI 如何生成报告..."
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                rows={6}
                className="text-sm font-mono resize-none"
              />
              <p className="text-xs text-muted-foreground">
                这个提示词将指导 AI 生成报告的风格和内容
              </p>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label>报告板块</Label>
                <span className="text-xs text-muted-foreground">
                  {sections.length} 个板块
                </span>
              </div>

              <div className="space-y-2">
                {sections.map((section, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-2 p-2 rounded-md border bg-muted/30"
                  >
                    <div className="flex-1">
                      <div className="font-medium text-sm">{section.title}</div>
                      {section.description && (
                        <div className="text-xs text-muted-foreground">
                          {section.description}
                        </div>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleRemoveSection(index)}
                      className="h-7 w-7"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>

              <div className="flex gap-2">
                <Input
                  placeholder="板块标题"
                  value={newSectionTitle}
                  onChange={(e) => setNewSectionTitle(e.target.value)}
                />
                <Input
                  placeholder="板块描述"
                  value={newSectionDesc}
                  onChange={(e) => setNewSectionDesc(e.target.value)}
                />
                <Button
                  onClick={handleAddSection}
                  disabled={!newSectionTitle}
                  size="icon"
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={handleCloseDialog}>
              取消
            </Button>
            <Button
              onClick={handleSave}
              disabled={!name || !systemPrompt || saveMutation.isPending}
            >
              {saveMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : editingTemplate ? (
                "保存"
              ) : (
                "创建"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
