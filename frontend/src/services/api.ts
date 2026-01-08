/**
 * API 客户端
 * 与后端 RESTful API 通信
 */

import type {
  APIResponse,
  Article,
  ArticleFilter,
  CrawlSource,
  DashboardStats,
  HealthStatus,
  KeywordCloudResponse,
  PaginatedResponse,
  PaginationParams,
  ParserDebugResult,
  PendingArticle,
  PendingStats,
  Report,
  ReportCreateRequest,
  ReportReference,
  ReportSSEEvent,
  ReportSection,
  ReportTemplate,
  ReportTemplateCreate,
  SearchResult,
  Sitemap,
  SourceCreateRequest,
  SourceStats,
  SourceUpdateRequest,
  Task,
  TaskEvent,
  TaskStats,
  TimeRangePreset,
  TimelineData,
} from "@/types"

const API_BASE_URL = "/api/v1"

/**
 * API 请求封装
 */
async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`

  const config: RequestInit = {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  }

  const response = await fetch(url, config)
  const data: APIResponse<T> = await response.json()

  if (!data.success) {
    throw new Error(data.error?.message || "请求失败")
  }

  return data.data as T
}

/**
 * 采集源 API
 */
export const sourcesApi = {
  /**
   * 获取采集源列表
   */
  list: (params: PaginationParams & {
    enabled?: boolean
    discovery_method?: string
    robots_status?: string
  }) =>
    request<PaginatedResponse<CrawlSource>>("/sources", {
      method: "GET",
    }).then((data) => {
      // 客户端实现筛选（简化处理）
      // 实际应在服务端处理
      return data
    }),

  /**
   * 获取单个采集源
   */
  get: (sourceId: number) =>
    request<CrawlSource>(`/sources/${sourceId}`),

  /**
   * 创建采集源
   */
  create: (data: SourceCreateRequest) =>
    request<CrawlSource>("/sources", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  /**
   * 批量导入采集源
   */
  bulkCreate: (baseUrls: string[], defaultParserConfig?: object) =>
    request<{ success_count: number; failed_count: number; errors: unknown[] }>("/sources/bulk", {
      method: "POST",
      body: JSON.stringify({ base_urls: baseUrls, default_parser_config: defaultParserConfig }),
    }),

  /**
   * 更新采集源
   */
  update: (sourceId: number, data: SourceUpdateRequest) =>
    request<CrawlSource>(`/sources/${sourceId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  /**
   * 删除采集源
   */
  delete: (sourceId: number) =>
    request<{ deleted_id: number }>(`/sources/${sourceId}`, {
      method: "DELETE",
    }),

  /**
   * 调试解析器配置
   */
  debugParser: (url: string, config: object) =>
    request<ParserDebugResult>("/sources/debug/parser", {
      method: "POST",
      body: JSON.stringify({ url, config }),
    }),

  /**
   * 获取 Sitemap 树
   */
  getSitemap: (sourceId: number, maxDepth = 3) =>
    request<{ url: string; lastmod: string | null; children: unknown[] }>(
      `/sources/${sourceId}/sitemap?max_depth=${maxDepth}`
    ),

  /**
   * 手动抓取 Sitemap
   */
  fetchSitemap: (sourceId: number) =>
    request<{ source_id: number; entries_found: number; fetched_at: string }>(
      `/sources/${sourceId}/sitemap/fetch`,
      { method: "POST" }
    ),

  /**
   * 获取 Robots 状态
   */
  getRobots: (sourceId: number) =>
    request<{ source_id: number; robots_status: string; crawl_delay: number | null }>(
      `/sources/${sourceId}/robots`
    ),

  /**
   * 手动获取 Robots.txt
   */
  fetchRobots: (sourceId: number) =>
    request<{ source_id: number; robots_status: string; crawl_delay: number | null }>(
      `/sources/${sourceId}/robots/fetch`,
      { method: "POST" }
    ),

  /**
   * 触发抓取
   */
  triggerCrawl: (sourceId: number, force = false) =>
    request<{ source_id: number; task_id: string; status: string }>(
      `/sources/${sourceId}/crawl?force=${force}`,
      { method: "POST" }
    ),

  /**
   * 获取源统计
   */
  getStats: (days = 30) =>
    request<SourceStats[]>(`/sources/stats/all?days=${days}`),
}

/**
 * 文章 API
 */
export const articlesApi = {
  /**
   * 获取文章列表
   */
  list: (params: PaginationParams & ArticleFilter) => {
    const searchParams = new URLSearchParams()
    searchParams.append("page", String(params.page))
    searchParams.append("page_size", String(params.page_size))
    if (params.sort_by) searchParams.append("sort_by", params.sort_by)
    if (params.sort_order) searchParams.append("sort_order", params.sort_order)

    return request<PaginatedResponse<Article>>(`/articles?${searchParams.toString()}`)
  },

  /**
   * 获取单篇文章
   */
  get: (articleId: number) =>
    request<Article>(`/articles/${articleId}`),

  /**
   * 创建文章
   */
  create: (data: { url: string; title: string; content?: string; publish_time?: string; author?: string; source_id: number }) =>
    request<Article>("/articles", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  /**
   * 更新文章
   */
  update: (
    articleId: number,
    data: {
      title?: string
      content?: string
      publish_time?: string
      author?: string
      status?: string
    }
  ) =>
    request<Article>(`/articles/${articleId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  /**
   * 删除文章
   */
  delete: (articleId: number) =>
    request<{ deleted_id: number }>(`/articles/${articleId}`, {
      method: "DELETE",
    }),

  /**
   * 重新爬取文章
   */
  refetch: (articleId: number) =>
    request<{ article: Article; status: string }>(`/articles/${articleId}/refetch`, {
      method: "POST",
    }),

  /**
   * 单条采集
   */
  fetchSingle: (url: string, source_id?: number) =>
    request<{ article: Article; status: string }>("/articles/fetch/single", {
      method: "POST",
      body: JSON.stringify({ url, source_id }),
    }),

  /**
   * 批量重试
   */
  bulkRetry: (articleIds?: number[], filter?: ArticleFilter) =>
    request<{ success_count: number; failed_count: number; errors: unknown[] }>("/articles/bulk/retry", {
      method: "POST",
      body: JSON.stringify({ article_ids: articleIds, filter }),
    }),

  /**
   * 批量删除
   */
  bulkDelete: (articleIds: number[]) =>
    request<{ success_count: number; failed_count: number; errors: unknown[] }>("/articles/bulk/delete", {
      method: "POST",
      body: JSON.stringify({ article_ids: articleIds }),
    }),

  /**
   * 清理低质量文章
   * 清理条件: 内容<50字符、无发布时间、发布时间在一年之外
   */
  cleanup: () =>
    request<{ success_count: number; failed_count: number; errors: unknown[] }>("/articles/cleanup", {
      method: "POST",
    }),

  /**
   * 获取相似文章
   */
  getSimilar: (articleId: number, limit = 10, threshold = 0.85) =>
    request<(Article & { similarity: number })[]>(
      `/articles/${articleId}/similar?limit=${limit}&threshold=${threshold}`
    ),

  /**
   * 状态统计
   */
  getStatusStats: () =>
    request<{ by_status: Record<string, number>; by_fetch_status: Record<string, number>; total: number }>(
      "/articles/stats/by-status"
    ),
}

/**
 * 报告 API（新系统）
 */
export const reportsApi = {
  /**
   * 获取报告列表
   */
  list: (limit = 20, offset = 0, status?: string) =>
    request<Report[]>(`/reports?limit=${limit}&offset=${offset}${status ? `&status=${status}` : ""}`),

  /**
   * 获取报告详情
   */
  get: (reportId: number) =>
    request<Report>(`/reports/${reportId}`),

  /**
   * 删除报告
   */
  delete: (reportId: number) =>
    request<{ deleted_id: number }>(`/reports/${reportId}`, {
      method: "DELETE",
    }),

  /**
   * 手动完成报告合并
   * 用于报告生成过程中SSE连接断开，板块已生成但未最终合并的情况
   */
  complete: (reportId: number) =>
    request<{ message: string; content_length: number; sections_count: number }>(`/reports/${reportId}/complete`, {
      method: "POST",
    }),

  /**
   * 生成报告（SSE 流式）
   * 任务在后台独立运行，不返回中止函数
   * 要停止任务，需要删除报告
   */
  generate: (
    request: ReportCreateRequest,
    onEvent: (event: ReportSSEEvent) => void,
    onComplete?: () => void,
    onError?: (error: string) => void
  ): void => {
    const url = `${API_BASE_URL}/reports/generate`

    ;(async () => {
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(request),
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const reader = response.body?.getReader()
        const decoder = new TextDecoder()
        let buffer = ""

        if (!reader) throw new Error("无法读取响应流")

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })

          const lines = buffer.split("\n")
          buffer = lines.pop() || ""

          let currentEvent: string | null = null
          let currentData: string | null = null

          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed) continue

            if (trimmed.startsWith("event:")) {
              currentEvent = trimmed.slice(6).trim()
            } else if (trimmed.startsWith("data:")) {
              currentData = trimmed.slice(5).trim()
            }

            if (currentEvent && currentData) {
              try {
                const parsedData = JSON.parse(currentData)
                onEvent({ event: currentEvent as ReportSSEEvent["event"], ...parsedData })
              } catch (e) {
                console.error("Failed to parse SSE data:", currentData, e)
              }
              currentEvent = null
              currentData = null

              // 检查是否完成
              if (currentEvent === "complete") {
                onComplete?.()
                return
              }
            }
          }
        }
      } catch (error) {
        if (error instanceof Error) {
          if (error.name === "AbortError") {
            console.log("Report generation connection closed")
          } else {
            onError?.(error.message)
          }
        }
      }
    })()
  },

  /**
   * 获取时间范围预设
   */
  getTimeRangePresets: () =>
    request<Record<string, { start: string; end: string }>>("/reports/presets/time-ranges"),

  /**
   * 报告模板 API
   */
  templates: {
    /**
     * 获取所有模板
     */
    list: (limit = 50) =>
      request<ReportTemplate[]>(`/reports/templates?limit=${limit}`),

    /**
     * 获取默认模板
     */
    getDefault: () =>
      request<ReportTemplate>("/reports/templates/default"),

    /**
     * 获取单个模板
     */
    get: (templateId: number) =>
      request<ReportTemplate>(`/reports/templates/${templateId}`),

    /**
     * 创建模板
     */
    create: (data: ReportTemplateCreate) =>
      request<ReportTemplate>("/reports/templates", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    /**
     * 更新模板
     */
    update: (templateId: number, data: Partial<ReportTemplateCreate>) =>
      request<ReportTemplate>(`/reports/templates/${templateId}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),

    /**
     * 删除模板
     */
    delete: (templateId: number) =>
      request<{ deleted_id: number }>(`/reports/templates/${templateId}`, {
        method: "DELETE",
      }),
  },

  // 旧版报告 API（兼容）
  /**
   * 获取报告引用（旧版）
   */
  getReferences: (reportId: string) =>
    request<ReportReference[]>(`/reports/${reportId}/references`),

  /**
   * 获取引用详情（旧版）
   */
  getReferenceDetail: (reportId: string, citationIndex: number) =>
    request<ReportReference>(`/reports/${reportId}/references/${citationIndex}`),

  /**
   * 更新报告状态（旧版）
   */
  updateStatus: (reportId: string, newStatus: "draft" | "published" | "archived") =>
    request<{ report_id: string; new_status: string }>(
      `/reports/${reportId}/status?new_status=${newStatus}`,
      { method: "PUT" }
    ),
}

/**
 * 搜索 API
 */
export const searchApi = {
  /**
   * 联网搜索
   */
  search: (query: string, timeRange = "w", maxResults = 10, region = "us-en") =>
    request<{ query: string; time_range: string; count: number; results: SearchResult[] }>(
      `/search?query=${encodeURIComponent(query)}&time_range=${timeRange}&max_results=${maxResults}&region=${region}`
    ),

  /**
   * 获取网页内容
   */
  fetchPage: (url: string, maxLength = 5000) =>
    request<{ url: string; content: string; length: number }>(
      `/search/fetch?url=${encodeURIComponent(url)}&max_length=${maxLength}`
    ),

  /**
   * 搜索结果一键入库
   */
  saveResult: (url: string, title: string, source_id?: number) =>
    request<{ article: Article; status: string }>("/search/save", {
      method: "POST",
      body: JSON.stringify({ url, title, source_id }),
    }),

  /**
   * 批量保存搜索结果
   */
  saveBatch: (
    query: string,
    timeRange = "w",
    maxResults = 10,
    region = "us-en"
  ) =>
    request<{
      query: string
      total: number
      created: number
      existing: number
      failed: number
      results: {
        created: Article[]
        existing: Article[]
        failed: Array<{ url: string; title: string; error: string }>
      }
    }>(
      `/search/save-batch?query=${encodeURIComponent(query)}&time_range=${timeRange}&max_results=${maxResults}&region=${region}`,
      { method: "POST" }
    ),

  /**
   * 上下文增强
   */
  enrich: (query: string, localArticleIds: number[], timeRange = "w", maxExternalResults = 5) =>
    request<{
      query: string
      local_count: number
      external_count: number
      merged_count: number
      conflicts_resolved: number
      combined_context: string
      external_results: SearchResult[]
    }>("/search/enrich", {
      method: "POST",
      body: JSON.stringify({
        query,
        local_article_ids: localArticleIds,
        time_range: timeRange,
        max_external_results: maxExternalResults,
      }),
    }),
}

/**
 * 仪表盘 API
 */
export const dashboardApi = {
  /**
   * 获取统计数据
   */
  getStats: () =>
    request<DashboardStats>("/dashboard/stats"),

  /**
   * 获取时间线数据
   */
  getTimeline: (days = 30) =>
    request<TimelineData[]>(`/dashboard/timeline?days=${days}`),

  /**
   * 获取热门源
   */
  getTopSources: (limit = 10, days = 7) =>
    request<SourceStats[]>(`/dashboard/top-sources?limit=${limit}&days=${days}`),

  /**
   * 获取最近活动
   */
  getRecentActivity: (limit = 20) =>
    request<
      Array<{ type: string; id: number; title: string; source_id: number; status: string; created_at: string }>
    >(`/dashboard/recent-activity?limit=${limit}`),

  /**
   * 获取系统健康状态
   */
  getHealth: () =>
    request<HealthStatus>("/dashboard/health"),

  /**
   * 获取关键词词云
   */
  getKeywordCloud: (period: "week" | "month", language: "zh" | "kk") =>
    request<KeywordCloudResponse>(`/dashboard/keywords/cloud?period=${period}&language=${language}`),
}

/**
 * Sitemap API
 */
export const sitemapsApi = {
  /**
   * 获取 Sitemap 列表
   */
  list: (sourceId?: number) =>
    request<Sitemap[]>(`/sitemaps${sourceId ? `?source_id=${sourceId}` : ""}`),

  /**
   * 获取 Sitemap 详情
   */
  get: (sitemapId: number) =>
    request<Sitemap>(`/sitemaps/${sitemapId}`),

  /**
   * 创建 Sitemap
   */
  create: (sourceId: number, url: string) =>
    request<{ id: number; url: string; source_id: number }>("/sitemaps", {
      method: "POST",
      body: JSON.stringify({ source_id: sourceId, url }),
    }),

  /**
   * 删除 Sitemap
   */
  delete: (sitemapId: number) =>
    request<{ deleted_id: number }>(`/sitemaps/${sitemapId}`, {
      method: "DELETE",
    }),

  /**
   * 从 robots.txt 获取 Sitemap
   */
  fetchRobots: (sourceId: number) =>
    request<{ source_id: number; sitemaps_found: number; sitemaps: Sitemap[] }>(
      `/sitemaps/fetch-robots/${sourceId}`,
      { method: "POST" }
    ),

  /**
   * 解析 Sitemap
   */
  parse: (sitemapId: number, recursive = true) =>
    request<{ sitemap_id: number; leaf_sitemaps: number[]; articles_found: number }>(
      `/sitemaps/parse/${sitemapId}?recursive=${recursive}`,
      { method: "POST" }
    ),

  /**
   * 导入 Sitemap 文章到待爬表
   */
  importArticles: (sitemapId: number) =>
    request<{
      sitemap_id: number
      articles_found: number
      articles_imported: number
      articles_existing: number
    }>(`/sitemaps/import-articles/${sitemapId}`, { method: "POST" }),

  /**
   * 同步源的所有 Sitemap 和文章
   */
  syncSource: (sourceId: number) =>
    request<{
      sitemaps_found: number
      articles_imported: number
      articles_existing: number
    }>(`/sitemaps/sync-source/${sourceId}`, { method: "POST" }),

  /**
   * 手动添加 Sitemap
   */
  addCustom: (sitemapUrl: string, sourceId?: number) =>
    request<{ sitemap_id: number; source_id: number; url: string; status: string }>(
      `/sitemaps/add-custom?sitemap_url=${encodeURIComponent(sitemapUrl)}${sourceId ? `&source_id=${sourceId}` : ""}`,
      { method: "POST" }
    ),

  /**
   * 获取待爬文章列表
   */
  listPending: (sourceId?: number, sitemapId?: number, status?: string, limit = 100, offset = 0) =>
    request<PendingArticle[]>(
      `/sitemaps/pending?limit=${limit}&offset=${offset}` +
      (sourceId ? `&source_id=${sourceId}` : "") +
      (sitemapId ? `&sitemap_id=${sitemapId}` : "") +
      (status ? `&status=${status}` : "")
    ),

  /**
   * 获取待爬文章统计
   */
  getPendingStats: (sourceId?: number) =>
    request<PendingStats>(`/sitemaps/pending/stats${sourceId ? `?source_id=${sourceId}` : ""}`),

  /**
   * 删除待爬文章
   */
  deletePending: (articleId: number) =>
    request<{ deleted_id: number }>(`/sitemaps/pending/${articleId}`, {
      method: "DELETE",
    }),

  /**
   * 爬取待爬文章
   */
  crawlPending: (sourceId: number, limit = 10) =>
    request<{ crawled: number; failed: number; skipped: number; total: number; message?: string }>(
      `/sitemaps/pending/crawl/${sourceId}?limit=${limit}`,
      { method: "POST" }
    ),

  /**
   * 爬取单个待爬文章
   */
  crawlSinglePending: (articleId: number) =>
    request<{ article: Article; status: string; message: string }>(
      `/sitemaps/pending/crawl-single/${articleId}`,
      { method: "POST" }
    ),

  /**
   * 全局批量爬取所有源的待爬文章 (SSE)
   */
  crawlAllPending: (
    limitPerSource = 10,
    onEvent?: (event: MessageEvent) => void,
    onComplete?: () => void,
    onError?: (error: Error) => void
  ) => {
    const url = `${API_BASE_URL}/sitemaps/pending/crawl-all?limit_per_source=${limitPerSource}`
    return fetchSSE(url, onEvent, onComplete, onError)
  },

  /**
   * 批量重试失败的待爬文章 (SSE)
   */
  retryFailed: (
    sourceId: number | undefined,
    limit = 10,
    onEvent?: (event: MessageEvent) => void,
    onComplete?: () => void,
    onError?: (error: Error) => void
  ) => {
    const url = `${API_BASE_URL}/sitemaps/pending/retry-failed?limit=${limit}${sourceId ? `&source_id=${sourceId}` : ""}`
    return fetchSSE(url, onEvent, onComplete, onError)
  },
}

/**
 * SSE 请求辅助函数
 */
function fetchSSE(
  url: string,
  onEvent?: (event: MessageEvent) => void,
  onComplete?: () => void,
  onError?: (error: Error) => void
): () => void {
  const eventSource = new EventSource(url, {
    withCredentials: true,
  })

  eventSource.onopen = () => {
    console.log("SSE connection opened")
  }

  eventSource.addEventListener("start", (e) => {
    onEvent?.(e as MessageEvent)
  })

  eventSource.addEventListener("source_start", (e) => {
    onEvent?.(e as MessageEvent)
  })

  eventSource.addEventListener("article_success", (e) => {
    onEvent?.(e as MessageEvent)
  })

  eventSource.addEventListener("article_failed", (e) => {
    onEvent?.(e as MessageEvent)
  })

  eventSource.addEventListener("article_skipped", (e) => {
    onEvent?.(e as MessageEvent)
  })

  eventSource.addEventListener("source_complete", (e) => {
    onEvent?.(e as MessageEvent)
  })

  eventSource.addEventListener("complete", (e) => {
    onEvent?.(e as MessageEvent)
    onComplete?.()
    eventSource.close()
  })

  eventSource.addEventListener("error", (e) => {
    onError?.(new Error("SSE connection error"))
    eventSource.close()
  })

  eventSource.onerror = (e) => {
    onError?.(new Error("SSE connection error"))
    eventSource.close()
  }

  // 返回关闭函数
  return () => {
    eventSource.close()
  }
}

/**
 * 任务 API
 */
export const tasksApi = {
  /**
   * 获取任务列表
   */
  list: (page = 1, pageSize = 20, status?: string, taskType?: string) => {
    const searchParams = new URLSearchParams()
    searchParams.append("page", String(page))
    searchParams.append("page_size", String(pageSize))
    if (status) searchParams.append("status_filter", status)
    if (taskType) searchParams.append("task_type", taskType)

    return request<PaginatedResponse<Task>>(`/tasks?${searchParams.toString()}`)
  },

  /**
   * 获取正在运行的任务
   */
  getRunning: (taskType?: string) =>
    request<Task[]>(`/tasks/running${taskType ? `?task_type=${taskType}` : ""}`),

  /**
   * 获取单个任务
   */
  get: (taskId: number) =>
    request<Task>(`/tasks/${taskId}`),

  /**
   * 创建任务
   */
  create: (taskType: string, title?: string, params?: Record<string, unknown>, autoStart = false) =>
    request<Task>(`/tasks?auto_start=${autoStart}`, {
      method: "POST",
      body: JSON.stringify({
        task_type: taskType,
        title,
        params,
      }),
    }),

  /**
   * 启动任务
   */
  start: (taskId: number) =>
    request<{ task_id: number; status: string }>(`/tasks/${taskId}/start`, {
      method: "POST",
    }),

  /**
   * 取消任务
   */
  cancel: (taskId: number) =>
    request<{ task_id: number; status: string }>(`/tasks/${taskId}`, {
      method: "DELETE",
    }),

  /**
   * 获取任务事件
   */
  getEvents: (taskId: number, limit = 100) =>
    request<TaskEvent[]>(`/tasks/${taskId}/events?limit=${limit}`),

  /**
   * 流式获取任务进度 (SSE)
   */
  streamProgress: (
    taskId: number,
    onEvent: (event: MessageEvent) => void,
    onComplete?: () => void,
    onError?: (error: Error) => void
  ) => {
    const url = `${API_BASE_URL}/tasks/${taskId}/stream`
    return fetchTaskSSE(url, onEvent, onComplete, onError)
  },

  /**
   * 流式执行批量爬取待爬文章 (SSE)
   */
  streamCrawlPending: (
    limitPerSource = 10,
    onEvent?: (event: MessageEvent) => void,
    onComplete?: () => void,
    onError?: (error: Error) => void
  ) => {
    const url = `${API_BASE_URL}/tasks/crawl-pending/stream?limit_per_source=${limitPerSource}`
    return fetchTaskSSE(url, onEvent, onComplete, onError)
  },

  /**
   * 流式执行批量重试失败文章 (SSE)
   */
  streamRetryFailed: (
    limit = 50,
    onEvent?: (event: MessageEvent) => void,
    onComplete?: () => void,
    onError?: (error: Error) => void
  ) => {
    const url = `${API_BASE_URL}/tasks/retry-failed/stream?limit=${limit}`
    return fetchTaskSSE(url, onEvent, onComplete, onError)
  },

  /**
   * 获取任务统计
   */
  getStats: () =>
    request<TaskStats>("/tasks/stats/summary"),
}

/**
 * 任务 SSE 请求辅助函数
 */
function fetchTaskSSE(
  url: string,
  onEvent?: (event: MessageEvent) => void,
  onComplete?: () => void,
  onError?: (error: Error) => void
): () => void {
  const eventSource = new EventSource(url, {
    withCredentials: true,
  })

  eventSource.onopen = () => {
    console.log("Task SSE connection opened")
  }

  // 任务创建事件
  eventSource.addEventListener("created", (e) => {
    onEvent?.(e as MessageEvent)
  })

  // 状态更新事件
  eventSource.addEventListener("status", (e) => {
    onEvent?.(e as MessageEvent)
  })

  // 任务事件
  eventSource.addEventListener("event", (e) => {
    onEvent?.(e as MessageEvent)
  })

  // 完成事件
  eventSource.addEventListener("complete", (e) => {
    onEvent?.(e as MessageEvent)
    onComplete?.()
    eventSource.close()
  })

  // 错误事件
  eventSource.addEventListener("error", (e) => {
    onError?.(new Error("Task error"))
    eventSource.close()
  })

  eventSource.onerror = (e) => {
    onError?.(new Error("SSE connection error"))
    eventSource.close()
  }

  // 返回关闭函数
  return () => {
    eventSource.close()
  }
}
