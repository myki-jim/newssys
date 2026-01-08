/**
 * 仪表盘相关 React Hooks
 */

import { useCallback, useEffect, useState } from "react"
import { dashboardApi } from "@/services/api"
import type {
  DashboardStats,
  HealthStatus,
  KeywordCloudData,
  SourceStats,
  TimelineData,
} from "@/types"

/**
 * 获取仪表盘统计数据
 */
export function useDashboardStats() {
  const [data, setData] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await dashboardApi.getStats()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取统计数据失败")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}

/**
 * 获取时间线数据
 */
export function useTimeline(days = 30) {
  const [data, setData] = useState<TimelineData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await dashboardApi.getTimeline(days)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取时间线数据失败")
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}

/**
 * 获取热门源
 */
export function useTopSources(limit = 10, days = 7) {
  const [data, setData] = useState<SourceStats[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await dashboardApi.getTopSources(limit, days)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取热门源失败")
    } finally {
      setLoading(false)
    }
  }, [limit, days])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}

/**
 * 获取最近活动
 */
export function useRecentActivity(limit = 20) {
  const [data, setData] = useState<
    Array<{ type: string; id: number; title: string; source_id: number; status: string; created_at: string }>
  >([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await dashboardApi.getRecentActivity(limit)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取最近活动失败")
    } finally {
      setLoading(false)
    }
  }, [limit])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}

/**
 * 获取系统健康状态
 */
export function useHealthStatus() {
  const [data, setData] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await dashboardApi.getHealth()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取健康状态失败")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}

/**
 * 获取关键词词云
 */
export function useKeywordCloud(period: "week" | "month", language: "zh" | "kk") {
  const [data, setData] = useState<KeywordCloudData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await dashboardApi.getKeywordCloud(period, language)
      setData(result.keywords)
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取关键词词云失败")
    } finally {
      setLoading(false)
    }
  }, [period, language])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}

/**
 * 获取所有关键词词云（4个组合）
 * 用于仪表盘显示
 */
export interface AllKeywordClouds {
  weekZh: KeywordCloudData[]
  weekKk: KeywordCloudData[]
  monthZh: KeywordCloudData[]
  monthKk: KeywordCloudData[]
}

export function useAllKeywordClouds() {
  const [data, setData] = useState<AllKeywordClouds>({
    weekZh: [],
    weekKk: [],
    monthZh: [],
    monthKk: [],
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [weekZh, weekKk, monthZh, monthKk] = await Promise.all([
        dashboardApi.getKeywordCloud("week", "zh"),
        dashboardApi.getKeywordCloud("week", "kk"),
        dashboardApi.getKeywordCloud("month", "zh"),
        dashboardApi.getKeywordCloud("month", "kk"),
      ])

      setData({
        weekZh: weekZh.keywords,
        weekKk: weekKk.keywords,
        monthZh: monthZh.keywords,
        monthKk: monthKk.keywords,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取关键词词云失败")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}
