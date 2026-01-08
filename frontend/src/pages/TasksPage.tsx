import { useState, useEffect } from "react"
import { tasksApi } from "@/services/api"
import type { Task, TaskStats, TaskEventType } from "@/types"
import { CheckCircle, XCircle, Clock, AlertCircle, Loader2 } from "lucide-react"

type TaskStatusType = "pending" | "running" | "completed" | "failed" | "cancelled"

const statusConfig: Record<TaskStatusType, { label: string; icon: React.ElementType; color: string }> = {
  pending: { label: "待执行", icon: Clock, color: "text-gray-500" },
  running: { label: "运行中", icon: Loader2, color: "text-blue-500 animate-spin" },
  completed: { label: "已完成", icon: CheckCircle, color: "text-green-500" },
  failed: { label: "失败", icon: XCircle, color: "text-red-500" },
  cancelled: { label: "已取消", icon: AlertCircle, color: "text-orange-500" },
}

export function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [stats, setStats] = useState<TaskStats | null>(null)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [events, setEvents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  // 轮询间隔（秒）
  const [pollInterval, setPollInterval] = useState(2)

  // 获取任务列表
  const fetchTasks = async () => {
    try {
      const response = await fetch("/api/v1/tasks?limit=20")
      const data = await response.json()
      if (data.success) {
        setTasks(data.data.items)
      }
    } catch (error) {
      console.error("获取任务列表失败:", error)
    }
  }

  // 获取统计信息
  const fetchStats = async () => {
    try {
      const response = await fetch("/api/v1/tasks/stats/summary")
      const data = await response.json()
      if (data.success) {
        setStats(data.data)
      }
    } catch (error) {
      console.error("获取统计信息失败:", error)
    }
  }

  // 获取任务事件
  const fetchEvents = async (taskId: number) => {
    try {
      const response = await fetch(`/api/v1/tasks/${taskId}/events?limit=100`)
      const data = await response.json()
      if (data.success) {
        setEvents(data.data)
      }
    } catch (error) {
      console.error("获取任务事件失败:", error)
    }
  }

  // 初始加载
  useEffect(() => {
    setLoading(true)
    Promise.all([fetchTasks(), fetchStats()]).finally(() => {
      setLoading(false)
    })
  }, [])

  // 定时刷新
  useEffect(() => {
    const interval = setInterval(() => {
      fetchTasks()
      fetchStats()
      if (selectedTask) {
        fetchEvents(selectedTask.id)
      }
    }, pollInterval * 1000)

    return () => clearInterval(interval)
  }, [pollInterval, selectedTask])

  // 选择任务
  const handleSelectTask = (task: Task) => {
    setSelectedTask(task)
    fetchEvents(task.id)
  }

  // 格式化时间
  const formatTime = (dateStr: string | null) => {
    if (!dateStr) return "-"
    return new Date(dateStr).toLocaleString("zh-CN")
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 标题栏 */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">任务管理</h1>
        <div className="flex items-center gap-2">
          <label className="text-sm text-muted-foreground">刷新间隔:</label>
          <select
            value={pollInterval}
            onChange={(e) => setPollInterval(Number(e.target.value))}
            className="border rounded px-2 py-1 text-sm"
          >
            <option value={1}>1秒</option>
            <option value={2}>2秒</option>
            <option value={5}>5秒</option>
            <option value={10}>10秒</option>
          </select>
        </div>
      </div>

      {/* 统计卡片 */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="border rounded-lg p-4">
            <div className="text-sm text-muted-foreground">待执行</div>
            <div className="text-2xl font-bold">{stats.pending}</div>
          </div>
          <div className="border rounded-lg p-4">
            <div className="text-sm text-muted-foreground">运行中</div>
            <div className="text-2xl font-bold text-blue-500">{stats.running}</div>
          </div>
          <div className="border rounded-lg p-4">
            <div className="text-sm text-muted-foreground">已完成</div>
            <div className="text-2xl font-bold text-green-500">{stats.completed}</div>
          </div>
          <div className="border rounded-lg p-4">
            <div className="text-sm text-muted-foreground">失败</div>
            <div className="text-2xl font-bold text-red-500">{stats.failed}</div>
          </div>
        </div>
      )}

      {/* 任务列表和详情 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 任务列表 */}
        <div className="border rounded-lg">
          <div className="border-b p-4">
            <h2 className="text-lg font-semibold">最近任务</h2>
          </div>
          <div className="divide-y max-h-[600px] overflow-y-auto">
            {tasks.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">
                暂无任务
              </div>
            ) : (
              tasks.map((task) => {
                const config = statusConfig[task.status as TaskStatusType]
                const Icon = config.icon

                return (
                  <div
                    key={task.id}
                    className={`p-4 cursor-pointer transition-colors ${
                      selectedTask?.id === task.id ? "bg-muted" : "hover:bg-muted/50"
                    }`}
                    onClick={() => handleSelectTask(task)}
                  >
                    <div className="flex items-start gap-3">
                      <Icon className={`w-5 h-5 mt-0.5 ${config.color}`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium truncate">{task.title || task.task_type}</span>
                          <span className={`text-xs px-2 py-0.5 rounded ${config.color} bg-opacity-10`}>
                            {config.label}
                          </span>
                        </div>
                        <div className="mt-1 text-sm text-muted-foreground">
                          {task.task_type} · 创建于 {formatTime(task.created_at)}
                        </div>
                        {task.status === "running" && task.progress_total > 0 && (
                          <div className="mt-2">
                            <div className="flex items-center justify-between text-xs mb-1">
                              <span>进度</span>
                              <span>{task.progress_current}/{task.progress_total}</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-1.5">
                              <div
                                className="bg-blue-500 h-1.5 rounded-full transition-all"
                                style={{
                                  width: `${(task.progress_current / task.progress_total) * 100}%`,
                                }}
                              />
                            </div>
                          </div>
                        )}
                        {task.error_message && (
                          <div className="mt-2 text-xs text-red-500 truncate">
                            {task.error_message}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* 任务详情 */}
        <div className="border rounded-lg">
          <div className="border-b p-4">
            <h2 className="text-lg font-semibold">任务详情</h2>
          </div>
          {selectedTask ? (
            <div className="p-4 space-y-4 max-h-[600px] overflow-y-auto">
              {/* 基本信息 */}
              <div className="space-y-2">
                <h3 className="font-medium">基本信息</h3>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-muted-foreground">任务ID:</span>
                    <span className="ml-2">{selectedTask.id}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">类型:</span>
                    <span className="ml-2">{selectedTask.task_type}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">状态:</span>
                    <span className="ml-2">{statusConfig[selectedTask.status as TaskStatusType]?.label}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">创建时间:</span>
                    <span className="ml-2">{formatTime(selectedTask.created_at)}</span>
                  </div>
                  {selectedTask.started_at && (
                    <div>
                      <span className="text-muted-foreground">开始时间:</span>
                      <span className="ml-2">{formatTime(selectedTask.started_at)}</span>
                    </div>
                  )}
                  {selectedTask.completed_at && (
                    <div>
                      <span className="text-muted-foreground">完成时间:</span>
                      <span className="ml-2">{formatTime(selectedTask.completed_at)}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* 参数 */}
              {selectedTask.params && Object.keys(selectedTask.params).length > 0 && (
                <div className="space-y-2">
                  <h3 className="font-medium">参数</h3>
                  <pre className="text-xs bg-muted p-2 rounded overflow-x-auto">
                    {JSON.stringify(selectedTask.params, null, 2)}
                  </pre>
                </div>
              )}

              {/* 结果 */}
              {selectedTask.result && Object.keys(selectedTask.result).length > 0 && (
                <div className="space-y-2">
                  <h3 className="font-medium">结果</h3>
                  <pre className="text-xs bg-muted p-2 rounded overflow-x-auto">
                    {JSON.stringify(selectedTask.result, null, 2)}
                  </pre>
                </div>
              )}

              {/* 事件日志 */}
              <div className="space-y-2">
                <h3 className="font-medium">执行日志</h3>
                <div className="border rounded-lg max-h-[300px] overflow-y-auto">
                  {events.length === 0 ? (
                    <div className="p-4 text-sm text-muted-foreground text-center">
                      暂无日志
                    </div>
                  ) : (
                    <div className="divide-y">
                      {events.map((event) => (
                        <div key={event.id} className="p-2 text-sm">
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-muted-foreground">
                              {formatTime(event.created_at)}
                            </span>
                            <span className="px-2 py-0.5 rounded text-xs bg-muted">
                              {event.event_type}
                            </span>
                          </div>
                          {event.event_data && (
                            <pre className="mt-1 text-xs text-muted-foreground overflow-x-auto">
                              {JSON.stringify(event.event_data, null, 2)}
                            </pre>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-muted-foreground">
              请选择一个任务查看详情
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
