/**
 * 报告生成相关 React Hooks
 */

import { useCallback, useEffect, useState } from "react"
import { reportsApi } from "@/services/api"
import type {
  Report,
  ReportCreateRequest,
  ReportSSEEvent,
  ReportTemplate,
  ReportTemplateCreate,
  TimeRangePreset,
} from "@/types"

/**
 * 获取报告列表
 */
export function useReports(limit = 20, offset = 0, status?: string) {
  const [data, setData] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await reportsApi.list(limit, offset, status)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取报告列表失败")
    } finally {
      setLoading(false)
    }
  }, [limit, offset, status])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}

/**
 * 获取单个报告详情
 */
export function useReport(reportId: number | null) {
  const [data, setData] = useState<Report | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    if (!reportId) {
      setData(null)
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const result = await reportsApi.get(reportId)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取报告详情失败")
    } finally {
      setLoading(false)
    }
  }, [reportId])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}

/**
 * 报告生成 Hook（SSE 流式）
 */
export interface ReportEvent {
  title: string
  summary: string
  importance: number
  article_count?: number
}

export interface ReportGenerationState {
  status: "idle" | "generating" | "completed" | "error"
  reportId: number | null
  stage: string
  progress: number
  message: string
  totalArticles: number
  clusteredArticles: number
  eventCount: number
  keywords: string[]  // AI 生成的关键字列表
  events: ReportEvent[]  // 提取的事件列表
  sections: Array<{ title: string; content: string; description: string; event_count: number }>
  currentStreamingSection: { title: string; content: string } | null  // 当前正在流式生成的板块
  content: string
  error: string | null
}

export function useReportGenerate() {
  const [state, setState] = useState<ReportGenerationState>({
    status: "idle",
    reportId: null,
    stage: "",
    progress: 0,
    message: "",
    totalArticles: 0,
    clusteredArticles: 0,
    eventCount: 0,
    keywords: [],
    events: [],
    sections: [],
    currentStreamingSection: null,
    content: "",
    error: null,
  })

  const generate = useCallback((request: ReportCreateRequest) => {
    // 重置状态
    setState({
      status: "generating",
      reportId: null,
      stage: "initializing",
      progress: 0,
      message: "正在启动报告生成...",
      totalArticles: 0,
      clusteredArticles: 0,
      eventCount: 0,
      keywords: [],
      events: [],
      sections: [],
      currentStreamingSection: null,
      content: "",
      error: null,
    })

    // 启动后台生成任务（不返回 abort 函数）
    reportsApi.generate(
      request,
      (event: ReportSSEEvent) => {
        switch (event.event) {
          case "start":
            setState((prev) => ({
              ...prev,
              status: "generating",
              reportId: event.report_id,
            }))
            break

          case "state":
            setState((prev) => ({
              ...prev,
              status: "generating",
              stage: event.stage,
              progress: event.progress,
              message: event.message,
              totalArticles: event.data?.total_articles ?? prev.totalArticles,
              clusteredArticles: event.data?.clustered_articles ?? prev.clusteredArticles,
              eventCount: event.data?.event_count ?? prev.eventCount,
              // 保存关键字列表
              keywords: event.data?.keywords ?? prev.keywords,
              // 保存事件列表
              events: event.data?.events ?? prev.events,
              // 保存已完成的板块
              sections: event.data?.sections ?? prev.sections,
            }))
            break

          case "section_stream":
            // 处理AI流式输出
            setState((prev) => ({
              ...prev,
              currentStreamingSection: {
                title: event.section_title || "",
                content: event.accumulated_content || "",
              },
            }))
            break

          case "complete":
            setState((prev) => ({
              ...prev,
              status: "completed",
              stage: "completed",
              progress: 100,
              message: "报告生成完成",
              sections: event.sections,
              content: event.content,
              totalArticles: event.statistics.total_articles,
              clusteredArticles: event.statistics.clustered_articles,
              eventCount: event.statistics.event_count,
              // 保存事件列表（从完整结果中获取）
              events: event.events ?? prev.events,
              // 清空当前流式板块
              currentStreamingSection: null,
            }))
            break

          case "error":
            setState((prev) => ({
              ...prev,
              status: "error",
              error: event.error,
              message: `错误: ${event.error}`,
              currentStreamingSection: null,
            }))
            break
        }
      },
      () => {
        // 完成
        setState((prev) => ({ ...prev, status: "completed" }))
      },
      (error) => {
        // 错误
        setState((prev) => ({
          ...prev,
          status: "error",
          error,
          message: `错误: ${error}`,
        }))
      }
    )
  }, [])

  const reset = useCallback(() => {
    setState({
      status: "idle",
      reportId: null,
      stage: "",
      progress: 0,
      message: "",
      totalArticles: 0,
      clusteredArticles: 0,
      eventCount: 0,
      keywords: [],
      events: [],
      sections: [],
      content: "",
      error: null,
    })
  }, [])

  return {
    state,
    generate,
    reset,
    isGenerating: state.status === "generating",
  }
}

/**
 * 报告模板 Hooks
 */
export function useReportTemplates(limit = 50) {
  const [data, setData] = useState<ReportTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await reportsApi.templates.list(limit)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取模板列表失败")
    } finally {
      setLoading(false)
    }
  }, [limit])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}

export function useDefaultTemplate() {
  const [data, setData] = useState<ReportTemplate | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await reportsApi.templates.getDefault()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取默认模板失败")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}

export function useReportTemplate(templateId: number | null) {
  const [data, setData] = useState<ReportTemplate | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    if (!templateId) {
      setData(null)
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)
    try {
      const result = await reportsApi.templates.get(templateId)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取模板详情失败")
    } finally {
      setLoading(false)
    }
  }, [templateId])

  useEffect(() => {
    fetch()
  }, [fetch])

  const create = useCallback(async (templateData: ReportTemplateCreate) => {
    setError(null)
    try {
      const result = await reportsApi.templates.create(templateData)
      setData(result)
      return result
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "创建模板失败"
      setError(errorMsg)
      throw err
    }
  }, [])

  const update = useCallback(async (id: number, templateData: Partial<ReportTemplateCreate>) => {
    setError(null)
    try {
      const result = await reportsApi.templates.update(id, templateData)
      setData(result)
      return result
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "更新模板失败"
      setError(errorMsg)
      throw err
    }
  }, [])

  const remove = useCallback(async (id: number) => {
    setError(null)
    try {
      await reportsApi.templates.delete(id)
      if (data?.id === id) {
        setData(null)
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "删除模板失败"
      setError(errorMsg)
      throw err
    }
  }, [data])

  return { data, loading, error, refetch: fetch, create, update, remove }
}

/**
 * 时间范围预设 Hook
 */
export function useTimeRangePresets() {
  const [data, setData] = useState<Record<string, TimeRangePreset>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await reportsApi.getTimeRangePresets()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取时间预设失败")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}
