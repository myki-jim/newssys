/**
 * 待爬文章状态分布图组件
 * 使用饼图展示待爬文章状态分布
 */

import { Pie, PieChart, ResponsiveContainer, Cell, Tooltip } from "recharts"

interface StatusData {
  name: string
  value: number
}

interface StatusDistributionChartProps {
  data: StatusData[]
}

const STATUS_COLORS: Record<string, string> = {
  pending: "#3b82f6", // blue-500
  crawling: "#f59e0b", // amber-500
  completed: "#10b981", // green-500
  failed: "#ef4444", // red-500
  abandoned: "#6b7280", // gray-500
  null: "#9ca3af", // gray-400
}

const STATUS_LABELS: Record<string, string> = {
  pending: "待处理",
  crawling: "爬取中",
  completed: "已完成",
  failed: "失败",
  abandoned: "已放弃",
  null: "未分类",
}

const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ value: number; name: string }> }) => {
  if (active && payload && payload.length) {
    const data = payload[0]
    const total = payload.reduce((sum, p) => sum + p.value, 0)
    const percentage = ((data.value / total) * 100).toFixed(1)
    return (
      <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3">
        <p className="font-medium text-gray-900">{STATUS_LABELS[data.name] || data.name}</p>
        <p className="text-sm text-gray-600">数量: {data.value}</p>
        <p className="text-sm text-gray-600">占比: {percentage}%</p>
      </div>
    )
  }
  return null
}

export function StatusDistributionChart({ data }: StatusDistributionChartProps) {
  // 转换数据，过滤掉值为0的项
  const chartData = data
    .filter((item) => item.value > 0)
    .map((item) => ({
      name: item.name,
      value: item.value,
    }))

  const total = chartData.reduce((sum, item) => sum + item.value, 0)

  if (total === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-muted-foreground text-sm">
        暂无数据
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={180}>
      <PieChart>
        <Pie
          data={chartData}
          cx="50%"
          cy="50%"
          labelLine={false}
          label={(entry) => {
            const percentage = ((entry.value / total) * 100).toFixed(1)
            if (parseFloat(percentage) < 8) return null
            return `${percentage}%`
          }}
          outerRadius={65}
          fill="#8884d8"
          dataKey="value"
        >
          {chartData.map((entry, index) => (
            <Cell
              key={`cell-${index}`}
              fill={STATUS_COLORS[entry.name] || STATUS_COLORS.null}
            />
          ))}
        </Pie>
        <Tooltip content={<CustomTooltip />} />
      </PieChart>
    </ResponsiveContainer>
  )
}
