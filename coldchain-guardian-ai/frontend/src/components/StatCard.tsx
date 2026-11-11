import type { ReactNode } from 'react'

interface Props {
  label: string
  value: string | number
  sub?: string
  icon?: ReactNode
  accent?: boolean
  danger?: boolean
}

export default function StatCard({ label, value, sub, icon, accent, danger }: Props) {
  const border = danger ? 'border-red-300 bg-red-50' : accent ? 'border-blue-300 bg-blue-50' : 'border-gray-200 bg-white'
  const valCol = danger ? 'text-red-700' : accent ? 'text-blue-700' : 'text-gray-900'
  return (
    <div className={`rounded-xl border p-5 shadow-sm ${border}`}>
      <div className="flex items-start justify-between">
        <p className="text-sm font-medium text-gray-500">{label}</p>
        {icon && <span className="text-gray-400">{icon}</span>}
      </div>
      <p className={`mt-2 text-3xl font-bold tabular-nums ${valCol}`}>{value}</p>
      {sub && <p className="mt-1 text-xs text-gray-400">{sub}</p>}
    </div>
  )
}
