import { useState, useEffect, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Send, Globe, Database, Loader2, Plus, Trash2, MessageSquare, Search, FileText, Clock, ExternalLink } from "lucide-react"
import type { Conversation, Message, AgentState } from "@/types"
import { formatDateTime, formatRelativeTime } from "@/lib/utils"

export function ChatPage() {
  const queryClient = useQueryClient()
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(null)
  const [message, setMessage] = useState("")
  const [webSearchEnabled, setWebSearchEnabled] = useState(false)
  const [internalSearchEnabled, setInternalSearchEnabled] = useState(false)
  const [agentState, setAgentState] = useState<AgentState | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [currentResponse, setCurrentResponse] = useState("")
  const [streamingConversationId, setStreamingConversationId] = useState<number | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 获取对话列表 - 只在需要时刷新
  const { data: conversations, isLoading: conversationsLoading } = useQuery({
    queryKey: ["conversations"],
    queryFn: async () => {
      const res = await fetch("/api/v1/conversations")
      const data = await res.json()
      return data.success ? data.data : []
    },
  })

  // 获取当前对话的消息 - 只在需要时刷新
  const { data: messages, isLoading: messagesLoading } = useQuery({
    queryKey: ["messages", selectedConversationId],
    queryFn: async () => {
      if (!selectedConversationId) return []
      const res = await fetch(`/api/v1/conversations/${selectedConversationId}/messages`)
      const data = await res.json()
      return data.success ? data.data : []
    },
    enabled: !!selectedConversationId,
  })

  // 发送消息
  const sendMessageMutation = useMutation({
    mutationFn: async (message: string) => {
      setIsStreaming(true)
      setCurrentResponse("")
      setAgentState(null)

      const response = await fetch("/api/v1/conversations/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: selectedConversationId,
          message,
          web_search_enabled: webSearchEnabled,
          internal_search_enabled: internalSearchEnabled,
        }),
      })

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) throw new Error("No response body")

      let fullResponse = ""
      let tempConversationId: number | null = selectedConversationId

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split("\n")

        for (const line of lines) {
          if (!line.trim() || !line.startsWith("data:")) continue

          const data = line.replace("data:", "").trim()
          if (!data) continue

          try {
            const event = JSON.parse(data)

            if (event.type === "start") {
              tempConversationId = event.conversation_id
              setStreamingConversationId(event.conversation_id)
            } else if (event.type === "state") {
              setAgentState(event.data)
            } else if (event.type === "chunk") {
              const text = event.data.text
              fullResponse += text
              setCurrentResponse(fullResponse)
            } else if (event.type === "end") {
              // 不自动切换对话，只刷新列表
              queryClient.invalidateQueries({ queryKey: ["conversations"] })
              queryClient.invalidateQueries({ queryKey: ["messages"] })
            } else if (event.type === "error") {
              throw new Error(event.data.error)
            }
          } catch (e) {
            console.error("Failed to parse SSE data:", e)
          }
        }
      }

      // 不自动切换对话，让用户看到消息后再自己选择
      // 只在成功完成后刷新列表

      return fullResponse
    },
    onSuccess: () => {
      setIsStreaming(false)
      setAgentState(null)
      setStreamingConversationId(null)
      queryClient.invalidateQueries({ queryKey: ["conversations"] })
      queryClient.invalidateQueries({ queryKey: ["messages"] })
    },
    onError: () => {
      setIsStreaming(false)
      setAgentState(null)
      setStreamingConversationId(null)
    },
  })

  // 删除对话
  const deleteConversationMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/v1/conversations/${id}`, { method: "DELETE" })
      const data = await res.json()
      if (!data.success) throw new Error(data.message || "删除失败")
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["conversations"] })
      if (selectedConversationId) {
        setSelectedConversationId(null)
      }
    },
  })

  // 创建新对话
  const createNewConversation = () => {
    setSelectedConversationId(null)
    setAgentState(null)
    setCurrentResponse("")
  }

  // 发送消息
  const handleSendMessage = () => {
    if (!message.trim() || isStreaming) return
    sendMessageMutation.mutate(message)
    setMessage("")
  }

  // 滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, currentResponse, agentState])

  const currentConversation = conversations?.find((c) => c.id === selectedConversationId)
  const displayMessages = messages || []

  // 渲染搜索结果来源
  const renderSources = (agentState: AgentState | null | undefined) => {
    if (!agentState) return null

    const internalResults = agentState.internal_results || []
    const webResults = agentState.web_results || []

    if (internalResults.length === 0 && webResults.length === 0) {
      return null
    }

    return (
      <div className="mt-3 pt-2 border-t border-black/10 dark:border-white/10">
        <div className="text-xs font-medium mb-2 opacity-70">来源:</div>

        {internalResults.length > 0 && (
          <div className="mb-2">
            <div className="flex items-center gap-1 text-xs font-medium text-green-600 dark:text-green-400 mb-1.5">
              <Database className="h-3 w-3" />
              内部知识库 ({internalResults.length})
            </div>
            <div className="space-y-1">
              {internalResults.slice(0, 5).map((result, i) => (
                <a
                  key={i}
                  href={result.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start gap-2 text-xs group hover:bg-white/5 rounded p-1 -mx-1 transition-colors"
                >
                  <ExternalLink className="h-3 w-3 mt-0.5 flex-shrink-0 opacity-50 group-hover:opacity-100" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                      {result.title}
                    </div>
                    {result.publish_time && (
                      <div className="opacity-50 text-[10px]">{formatDateTime(result.publish_time)}</div>
                    )}
                  </div>
                </a>
              ))}
            </div>
          </div>
        )}

        {webResults.length > 0 && (
          <div>
            <div className="flex items-center gap-1 text-xs font-medium text-blue-600 dark:text-blue-400 mb-1.5">
              <Globe className="h-3 w-3" />
              联网搜索 ({webResults.length})
            </div>
            <div className="space-y-1">
              {webResults.slice(0, 5).map((result, i) => (
                <a
                  key={i}
                  href={result.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start gap-2 text-xs group hover:bg-white/5 rounded p-1 -mx-1 transition-colors"
                >
                  <ExternalLink className="h-3 w-3 mt-0.5 flex-shrink-0 opacity-50 group-hover:opacity-100" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                      {result.title}
                    </div>
                    {result.publish_time && (
                      <div className="opacity-50 text-[10px]">{formatDateTime(result.publish_time)}</div>
                    )}
                  </div>
                </a>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  // 渲染 Agent 状态步骤
  const renderAgentSteps = () => {
    if (!agentState) return null

    const steps = [
      { stage: "generating_keywords", label: "生成关键词", icon: "🔍" },
      { stage: "searching_internal", label: "内部搜索", icon: "📚" },
      { stage: "searching_web", label: "联网搜索", icon: "🌐" },
      { stage: "generating_response", label: "生成回答", icon: "✨" },
      { stage: "completed", label: "完成", icon: "✅" },
    ]

    const currentStage = agentState.stage
    const currentIndex = steps.findIndex(s => s.stage === currentStage)

    return (
      <div className="space-y-2 mb-4">
        <div className="text-sm font-medium text-muted-foreground mb-2">Agent 执行流程:</div>
        {steps.map((step, index) => {
          const isCompleted = index < currentIndex
          const isCurrent = index === currentIndex

          return (
            <div
              key={step.stage}
              className={`flex items-center gap-2 text-sm ${
                isCompleted ? "text-green-600" : isCurrent ? "text-blue-600" : "text-muted-foreground"
              }`}
            >
              <span className="w-5">{step.icon}</span>
              <span className="flex-1">{step.label}</span>
              {isCurrent && <Loader2 className="h-3 w-3 animate-spin" />}
              {isCompleted && <span className="text-xs">✓</span>}
            </div>
          )
        })}
        {agentState.keywords && agentState.keywords.length > 0 && (
          <div className="mt-2 p-2 bg-blue-50 dark:bg-blue-950 rounded text-xs">
            <span className="font-medium">关键词: </span>
            {agentState.keywords.map((kw, i) => (
              <span key={i} className="inline-block bg-blue-200 dark:bg-blue-800 px-2 py-0.5 rounded mr-1 mb-1">
                {kw}
              </span>
            ))}
          </div>
        )}
      </div>
    )
  }

  // 渲染搜索结果
  const renderSearchResults = () => {
    if (!agentState) return null

    const hasResults = (agentState.internal_results?.length > 0) || (agentState.web_results?.length > 0)

    if (!hasResults) return null

    return (
      <div className="space-y-3 mt-3">
        {agentState.internal_results && agentState.internal_results.length > 0 && (
          <div className="text-xs">
            <div className="font-medium text-green-600 dark:text-green-400 mb-1 flex items-center gap-1">
              <Database className="h-3 w-3" />
              内部知识库 ({agentState.internal_results.length} 篇)
            </div>
            {agentState.internal_results.slice(0, 3).map((result, i) => (
              <div key={i} className="p-2 bg-green-50 dark:bg-green-950/20 rounded mt-1">
                <div className="font-medium truncate">{result.title}</div>
                <div className="text-muted-foreground truncate">{result.url}</div>
              </div>
            ))}
          </div>
        )}
        {agentState.web_results && agentState.web_results.length > 0 && (
          <div className="text-xs">
            <div className="font-medium text-blue-600 dark:text-blue-400 mb-1 flex items-center gap-1">
              <Globe className="h-3 w-3" />
              联网搜索 ({agentState.web_results.length} 篇)
            </div>
            {agentState.web_results.slice(0, 3).map((result, i) => (
              <div key={i} className="p-2 bg-blue-50 dark:bg-blue-950/20 rounded mt-1">
                <div className="font-medium truncate">{result.title}</div>
                <div className="text-muted-foreground truncate">{result.url}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="flex h-full">
      {/* 对话列表 */}
      <div className="w-80 border-r flex flex-col">
        <div className="p-4 border-b">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">对话历史</h2>
            <Button variant="ghost" size="icon" onClick={createNewConversation} title="新对话">
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-2">
          {conversationsLoading ? (
            <div className="flex justify-center p-4">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : (
            conversations?.map((conv) => (
              <div
                key={conv.id}
                className={`p-3 rounded-lg cursor-pointer transition-colors ${
                  selectedConversationId === conv.id
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted hover:bg-muted/80"
                }`}
                onClick={() => setSelectedConversationId(conv.id)}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium truncate">{conv.title}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 opacity-50 hover:opacity-100"
                    onClick={(e) => {
                      e.stopPropagation()
                      deleteConversationMutation.mutate(conv.id)
                    }}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
                <div className="text-xs opacity-70 mt-1 flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {formatDateTime(conv.updated_at)}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 主对话区域 */}
      <div className="flex-1 flex flex-col">
        {/* 搜索模式开关 */}
        <div className="border-b p-4">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Globe className="h-4 w-4" />
              <Label htmlFor="web-search">联网搜索</Label>
              <Switch
                id="web-search"
                checked={webSearchEnabled}
                onCheckedChange={setWebSearchEnabled}
                disabled={isStreaming}
              />
            </div>
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4" />
              <Label htmlFor="internal-search">内部知识库</Label>
              <Switch
                id="internal-search"
                checked={internalSearchEnabled}
                onCheckedChange={setInternalSearchEnabled}
                disabled={isStreaming}
              />
            </div>
            <div className="ml-auto text-sm text-muted-foreground">
              {webSearchEnabled || internalSearchEnabled ? (
                <span className="flex items-center gap-1 text-blue-600">
                  <MessageSquare className="h-3 w-3" />
                  Agent模式
                </span>
              ) : (
                "直接对话"
              )}
            </div>
          </div>
        </div>

        {/* 消息列表 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {!selectedConversationId && !currentResponse && !isStreaming && (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              <div className="text-center">
                <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>选择一个对话或发送新消息开始</p>
                {(webSearchEnabled || internalSearchEnabled) && (
                  <p className="text-sm mt-2 text-blue-600">Agent模式已启用，将使用搜索增强回答</p>
                )}
              </div>
            </div>
          )}

          {displayMessages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <Card
                className={`max-w-[80%] p-3 ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}
              >
                <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                {renderSources(msg.agent_state)}
                <div className="text-xs opacity-50 mt-2 flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {formatDateTime(msg.created_at)}
                </div>
              </Card>
            </div>
          ))}

          {/* Agent 流程状态指示器 */}
          {agentState && (
            <div className="flex justify-center">
              <Card className="p-4 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950 dark:to-indigo-950 border-blue-200 dark:border-blue-800 w-full max-w-md">
                <div className="flex items-center gap-3 text-sm">
                  <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
                  <div className="flex-1">
                    <div className="font-medium">{agentState.message}</div>
                    {agentState.progress > 0 && (
                      <div className="mt-2 w-full bg-blue-200 dark:bg-blue-800 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all"
                          style={{ width: `${agentState.progress}%` }}
                        />
                      </div>
                    )}
                  </div>
                </div>
                {renderAgentSteps()}
                {renderSearchResults()}
              </Card>
            </div>
          )}

          {/* 当前流式响应 */}
          {currentResponse && (
            <div className="flex justify-start">
              <Card className="max-w-[80%] p-3 bg-muted">
                <div className="text-sm whitespace-pre-wrap">{currentResponse}</div>
                {isStreaming && (
                  <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    正在生成...
                  </div>
                )}
              </Card>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* 输入框 */}
        <div className="border-t p-4">
          <div className="flex gap-2">
            <Input
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault()
                  handleSendMessage()
                }
              }}
              placeholder="输入消息... (Enter发送，Shift+Enter换行)"
              disabled={isStreaming}
              className="flex-1"
            />
            <Button
              onClick={handleSendMessage}
              disabled={!message.trim() || isStreaming}
            >
              {isStreaming ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
