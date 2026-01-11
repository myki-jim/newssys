/**
 * 热门采集源饼图组件
 * 使用 Recharts 展示各采集源的文章数量占比
 */

import { Pie, PieChart, ResponsiveContainer, Cell, Tooltip } from "recharts"
import type { SourceStats } from "@/types"

interface HotSourcesPieChartProps {
  data: SourceStats[]
}

// 预定义颜色方案
const COLORS = [
  "#3b82f6", // blue-500
  "#10b981", // green-500
  "#f59e0b", // amber-500
  "#ef4444", // red-500
  "#8b5cf6", // violet-500
  "#ec4899", // pink-500
  "#06b6d4", // cyan-500
  "#f97316", // orange-500
  "#84cc16", // lime-500
  "#6366f1", // indigo-500
  "#14b8a6", // teal-500
  "#d946ef", // fuchsia-500
]

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ value: number; name: string; payload: SourceStats }> }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload
    const total = payload.reduce((sum, p) => sum + p.value, 0)
    const percentage = ((data.value / total) * 100).toFixed(1)
    return (
      <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3">
        <p className="font-medium text-gray-900">{data.name}</p>
        <p className="text-sm text-gray-600">文章数: {data.value}</p>
        <p className="text-sm text-gray-600">占比: {percentage}%</p>
      </div>
    )
  }
  return null
}

export function HotSourcesPieChart({ data }: HotSourcesPieChartProps) {
  // 转换数据为饼图格式
  const chartData = data.map((source) => ({
    name: source.site_name,
    value: source.total_articles,
    sourceData: source,
  }))

  return (
    <ResponsiveContainer width="100%" height={180}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          labelLine={false}
          label={(entry) => {
            const percentage = ((entry.value / chartData.reduce((sum, d) => sum + d.value, 0)) * 100).toFixed(1)
            if (parseFloat(percentage) < 8) return null // 小于8%不显示标签
            return `${percentage}%`
          }}
          outerRadius={65}
          fill="#8884d8"
          dataKey="value"
        >
          {chartData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
          ))}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
      </PieChart>
    </ResponsiveContainer>
  )
}
