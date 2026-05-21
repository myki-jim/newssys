import { Info, Shield, Github, ExternalLink } from "lucide-react"

export function AboutPage() {
  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold">关于系统</h2>
        <p className="text-muted-foreground mt-1">开源情报智能分析系统</p>
      </div>

      <div className="space-y-6">
        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <Info className="h-6 w-6 text-primary" />
            <h3 className="text-lg font-semibold">系统信息</h3>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between py-2 border-b">
              <span className="text-muted-foreground">系统名称</span>
              <span className="font-medium">开源情报智能分析系统</span>
            </div>
            <div className="flex justify-between py-2 border-b">
              <span className="text-muted-foreground">版本</span>
              <span className="font-medium">v2.1.0</span>
            </div>
            <div className="flex justify-between py-2 border-b">
              <span className="text-muted-foreground">AI Agent</span>
              <span className="font-medium">开源情报智能分析agent</span>
            </div>
            <div className="flex justify-between py-2 border-b">
              <span className="text-muted-foreground">前端框架</span>
              <span className="font-medium">React 18 + TypeScript + Vite</span>
            </div>
            <div className="flex justify-between py-2 border-b">
              <span className="text-muted-foreground">UI 组件库</span>
              <span className="font-medium">Radix UI + TailwindCSS</span>
            </div>
            <div className="flex justify-between py-2">
              <span className="text-muted-foreground">后端框架</span>
              <span className="font-medium">FastAPI + Python 3.12</span>
            </div>
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <Shield className="h-6 w-6 text-primary" />
            <h3 className="text-lg font-semibold">开源协议</h3>
          </div>
          <p className="text-sm text-muted-foreground mb-4">
            本项目基于 MIT 协议开源，允许自由使用、修改和分发。
          </p>
          <div className="bg-muted rounded-lg p-4 text-xs font-mono text-muted-foreground">
            MIT License — Copyright (c) 2026 开源情报智能分析系统
          </div>
        </div>

        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <Github className="h-6 w-6 text-primary" />
            <h3 className="text-lg font-semibold">社区</h3>
          </div>
          <p className="text-sm text-muted-foreground mb-3">
            欢迎参与项目贡献和讨论。
          </p>
          <a
            href="https://github.com/siteboon/claudecodeui"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
          >
            <ExternalLink className="h-4 w-4" />
            GitHub 仓库
          </a>
        </div>
      </div>
    </div>
  )
}
