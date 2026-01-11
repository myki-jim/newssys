/**
 * 类型定义
 * 与后端 API Schema 保持一致
 */

// ============================================================================
// 通用类型
// ============================================================================

export interface APIResponse<T = unknown> {
  success: boolean
  data?: T
  error?: APIError
}

export interface APIError {
  code: string
  message: string
  details?: Record<string, unknown>
}

export interface PaginatedResponse<T = unknown> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface PaginationParams {
  page: number
  page_size: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

// ============================================================================
// 采集源类型
// ============================================================================

export interface ParserConfig {
  title_selector: string
  content_selector: string
  publish_time_selector?: string
  author_selector?: string
  list_selector?: string
  url_selector?: string
  encoding: string
}

export interface CrawlSource {
  id: number
  site_name: string
  base_url: string
  parser_config: ParserConfig
  enabled: boolean
  crawl_interval: number
  robots_status: 'pending' | 'compliant' | 'restricted' | 'not_found' | 'error'
  crawl_delay: number | null
  robots_fetched_at: string | null
  sitemap_url: string | null
  sitemap_last_fetched: string | null
  sitemap_entry_count: number | null
  last_crawled_at: string | null
  success_count: number
  failure_count: number
  last_error: string | null
  discovery_method: 'sitemap' | 'list' | 'hybrid'
  extra_data: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface SourceCreateRequest {
  site_name: string
  base_url: string
  parser_config: ParserConfig
  enabled?: boolean
  crawl_interval?: number
}

export interface SourceUpdateRequest {
  site_name?: string
  base_url?: string
  parser_config?: ParserConfig
  enabled?: boolean
  crawl_interval?: number
}

// ============================================================================
// 文章类型
// ============================================================================

export type ArticleStatus = 'raw' | 'processed' | 'synced' | 'failed'
export type FetchStatus = 'pending' | 'success' | 'retry' | 'failed'

export interface Article {
  id: number
  url_hash: string
  url: string
  title: string
  content: string | null
  content_hash: string | null
  publish_time: string | null
  author: string | null
  source_id: number
  status: ArticleStatus
  fetch_status: FetchStatus
  error_message: string | null
  error_msg: string | null
  crawled_at: string | null
  processed_at: string | null
  synced_at: string | null
  retry_count: number
  last_retry_at: string | null
  extra_data: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface ArticleFilter {
  source_ids?: number[]
  source_search?: string
  status?: string
  fetch_status?: string
  keyword?: string
  url_hash?: string
  date_range?: {
    start: string
    end: string
  }
  publish_time_range?: {
    start: string
    end: string
  }
  min_score?: number
}

// ============================================================================
// Sitemap 类型
// ============================================================================

export type SitemapFetchStatus = 'pending' | 'success' | 'failed'

export interface Sitemap {
  id: number
  source_id: number
  url: string
  last_fetched: string | null
  fetch_status: SitemapFetchStatus
  article_count: number
  created_at: string
  updated_at: string
}

export type PendingArticleStatus = 'pending' | 'crawling' | 'completed' | 'failed' | 'abandoned'

export interface PendingArticle {
  id: number
  source_id: number
  sitemap_id: number | null
  url: string
  url_hash: string
  title: string | null
  publish_time: string | null
  status: PendingArticleStatus
  created_at: string
  updated_at: string
}

export interface PendingStats {
  total: number
  pending: number
  crawling: number
  completed: number
  failed: number
  abandoned: number
}

// ============================================================================
// 对话类型
// ============================================================================

export interface Conversation {
  id: number
  title: string
  mode: string
  web_search_enabled: boolean
  internal_search_enabled: boolean
  created_at: string
  updated_at: string
}

export interface Message {
  id: number
  conversation_id: number
  role: 'user' | 'assistant' | 'system'
  content: string
  agent_state: AgentState | null
  search_results: SearchResults | null
  created_at: string
}

export interface AgentState {
  stage: 'generating_keywords' | 'searching_internal' | 'searching_web' | 'generating_response' | 'completed' | 'direct_chat'
  keywords: string[]
  internal_results: SearchResult[]
  web_results: SearchResult[]
  progress: number
  total: number
  message: string
}

export interface SearchResult {
  title: string
  url: string
  publish_time?: string
  content?: string
  snippet?: string
}

export interface SearchResults {
  keywords: string[]
  internal_results: SearchResult[]
  web_results: SearchResult[]
}

// ============================================================================
// 报告类型
// ============================================================================

// 新报告生成系统类型
export type ReportStatus = 'draft' | 'generating' | 'completed' | 'failed'
export type ReportAgentStage =
  | 'initializing'
  | 'filtering_articles'
  | 'clustering_articles'
  | 'extracting_events'
  | 'generating_sections'
  | 'merging_report'
  | 'completed'

export interface Report {
  id: number
  title: string
  time_range_start: string
  time_range_end: string
  template_id: number | null
  custom_prompt: string | null
  language: string
  total_articles: number
  clustered_articles: number
  event_count: number
  content: string | null
  sections: ReportSection[]
  status: ReportStatus
  agent_stage: ReportAgentStage
  agent_progress: number
  agent_message: string
  error_message: string | null
  created_at: string
  updated_at: string
  completed_at: string | null
}

export interface ReportSection {
  title: string
  content: string
  description: string
  event_count: number
}

export interface ReportCreateRequest {
  title: string
  time_range_start: string
  time_range_end: string
  template_id?: number | null
  custom_prompt?: string | null
  max_events?: number
  language?: 'zh' | 'kk'
}

export interface ReportTemplate {
  id: number
  name: string
  description: string | null
  system_prompt: string
  section_template: SectionTemplate[]
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface SectionTemplate {
  title: string
  description: string
}

export interface ReportTemplateCreate {
  name: string
  description?: string | null
  system_prompt: string
  section_template: SectionTemplate[]
}

export interface ReportAgentState {
  stage: ReportAgentStage
  progress: number
  total: number
  message: string
  data: Record<string, unknown>
}

export interface ReportEvent {
  id: number
  report_id: number
  event_title: string
  event_summary: string
  article_count: number
  keywords: string[]
  importance_score: number
}

export interface TimeRangePreset {
  name: string
  start: string
  end: string
}

// SSE 事件类型
export interface ReportSSEStartEvent {
  event: 'start'
  report_id: number
}

export interface ReportSSEStateEvent {
  event: 'state'
  stage: ReportAgentStage
  progress: number
  message: string
  data: {
    total_articles?: number
    clustered_articles?: number
    event_count?: number
    keywords?: string[]  // AI 生成的关键字列表
    events?: Array<{
      title: string
      summary: string
      importance: number
      article_count?: number
    }>
    sections?: ReportSection[]  // 已完成的板块
  } & Record<string, unknown>
}

export interface ReportSSESectionStreamEvent {
  event: 'section_stream'
  section_title: string  // 当前正在生成的板块标题
  chunk: string  // 本次新增的内容片段
  accumulated_content: string  // 累积的完整内容
}

export interface ReportSSECompleteEvent {
  event: 'complete'
  content: string
  sections: ReportSection[]
  events?: Array<{
    title: string
    summary: string
    importance: number
    article_count?: number
  }>
  statistics: {
    total_articles: number
    clustered_articles: number
    event_count: number
  }
}

export interface ReportSSEErrorEvent {
  event: 'error'
  error: string
}

export type ReportSSEEvent =
  | ReportSSEStartEvent
  | ReportSSEStateEvent
  | ReportSSESectionStreamEvent
  | ReportSSECompleteEvent
  | ReportSSEErrorEvent

// 旧报告类型（兼容）
export interface LegacyReport {
  id: string
  title: string
  template_id: string | null
  time_range: string | null
  article_count: number
  content: string | null
  status: ReportStatus
  generated_at: string | null
  created_at: string
  updated_at: string
}

export interface ReportReference {
  id: number
  report_id: string
  article_id: number
  citation_index: number
  context_snippet: string | null
  citation_position: number | null
  article_title: string
  article_url: string
  article_content: string | null
  article_publish_time: string | null
  article_author: string | null
  article_source: string
}

export interface ReportGenerateRequest {
  title: string
  template_id?: string
  time_range?: string
  source_ids?: number[]
  keywords?: string[]
  max_articles?: number
  enable_search?: boolean
  search_query?: string
  context_text?: string
}

// ============================================================================
// 词云类型
// ============================================================================

export interface KeywordCloudData {
  keyword: string
  weight: number
  language: 'zh' | 'kk'
}

export interface KeywordCloudResponse {
  period: 'week' | 'month'
  language: 'zh' | 'kk'
  keywords: KeywordCloudData[]
  from_date: string
  to_date: string
  total_articles: number
}

// ============================================================================
// SSE 事件类型
// ============================================================================

export interface SSEStartEvent {
  event: 'start'
  report_id: string
}

export interface SSEProgressEvent {
  event: 'progress'
  stage: 'aggregation' | 'search' | 'generation' | 'saving'
  progress: number
  message: string
}

export interface SSEChunkEvent {
  event: 'chunk'
  content: string
  accumulated: string
}

export interface SSECompleteEvent {
  event: 'complete'
  report_id: string
  article_count: number
}

export interface SSEErrorEvent {
  event: 'error'
  error: string
}

export type SSEEvent =
  | SSEStartEvent
  | SSEProgressEvent
  | SSEChunkEvent
  | SSECompleteEvent
  | SSEErrorEvent

// ============================================================================
// 统计类型
// ============================================================================

export interface DashboardStats {
  total_sources: number
  active_sources: number
  total_articles: number
  today_articles: number
  failed_articles: number
  total_reports: number
  avg_processing_time: number | null
  storage_used_mb: number | null
}

export interface SourceStats {
  source_id: number
  site_name: string
  total_articles: number
  success_count: number
  failure_count: number
  success_rate: number
  last_crawled_at: string | null
}

export interface TimelineData {
  date: string
  total: number
  processed: number
  failed: number
}

export interface HealthStatus {
  status: 'healthy' | 'warning' | 'critical'
  issues: string[]
  metrics: {
    pending_articles: number
    retry_queue: number
    failure_rate_24h: number
  }
}

// ============================================================================
// 搜索类型
// ============================================================================

export interface SearchResultItem {
  title: string
  url: string
  snippet: string
  published_date: string | null
  source: string | null
}

// ============================================================================
// 调试类型
// ============================================================================

export interface ParserDebugResult {
  url: string
  title: string | null
  content: string | null
  publish_time: string | null
  author: string | null
  error: string | null
  raw_html_length: number | null
  extraction_time_ms: number | null
}

// ============================================================================
// 任务类型
// ============================================================================

export type TaskStatusType = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type TaskTypeType = 'crawl_pending' | 'retry_failed' | 'crawl_source' | 'search_import' | 'sitemap_sync' | 'auto_search' | 'cleanup_low_quality'
export type TaskEventType = 'created' | 'started' | 'progress' | 'completed' | 'failed' | 'cancelled' | 'info'

export interface Task {
  id: number
  task_type: TaskTypeType
  status: TaskStatusType
  title: string | null
  params: Record<string, unknown>
  result: Record<string, unknown> | null
  progress_current: number
  progress_total: number
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface TaskEvent {
  id: number
  task_id: number
  event_type: TaskEventType
  event_data: Record<string, unknown> | null
  created_at: string
}

export interface TaskStats {
  pending: number
  running: number
  completed: number
  failed: number
  cancelled: number
  total_types: number
  registered_types: string[]
}
