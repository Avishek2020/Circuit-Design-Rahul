import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, DollarSign, Package, Thermometer, Truck, TrendingUp } from 'lucide-react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { api } from '../api'
import Spinner from '../components/Spinner'
import StatCard from '../components/StatCard'

const STATUS_COLOURS: Record<string, string> = {
  delivered:          '#22c55e',
  in_transit:         '#3b82f6',
  failed_inspection:  '#ef4444',
  delayed:            '#f97316',
  pending:            '#a855f7',
}

export default function FleetDashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['fleetSummary'],
    queryFn:  api.fleetSummary,
  })

  if (isLoading) return <Spinner label="Loading fleet data…" />
  if (error || !data) return <p className="py-16 text-center text-red-500">Failed to load fleet data.</p>

  const excPct = ((data.shipments_with_excursion / data.total_shipments) * 100).toFixed(1)
  const pieData = Object.entries(data.status_breakdown).map(([name, value]) => ({ name, value }))

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Fleet Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">Real-time cold-chain health across all shipments</p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <StatCard label="Total Shipments"  value={data.total_shipments}            icon={<Package   size={18} />} />
        <StatCard label="Excursions"       value={data.shipments_with_excursion}   icon={<Thermometer size={18} />} danger={data.shipments_with_excursion > 0} sub={`${excPct}% of fleet`} />
        <StatCard label="Incidents"        value={data.total_incidents}            icon={<AlertTriangle size={18} />} danger={data.total_incidents > 0} />
        <StatCard label="Financial Loss"   value={`$${(data.total_financial_loss_usd / 1000).toFixed(0)}k`} icon={<DollarSign size={18} />} danger={data.total_financial_loss_usd > 0} />
        <StatCard label="Maint. Overdue"   value={data.trucks_maintenance_overdue.length} icon={<Truck size={18} />} danger={data.trucks_maintenance_overdue.length > 0} sub="trucks" />
        <StatCard label="Reg. Reportable"  value={data.regulatory_reportable_incidents} icon={<TrendingUp size={18} />} accent={data.regulatory_reportable_incidents > 0} />
      </div>

      {/* Status pie + overdue trucks */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold text-gray-700">Shipment Status Breakdown</h2>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={85} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
                {pieData.map(entry => (
                  <Cell key={entry.name} fill={STATUS_COLOURS[entry.name] ?? '#94a3b8'} />
                ))}
              </Pie>
              <Tooltip formatter={(v: number, n: string) => [v, n.replace('_', ' ')]} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold text-gray-700">Maintenance Overdue Trucks</h2>
          {data.trucks_maintenance_overdue.length === 0 ? (
            <p className="text-sm text-green-600">All trucks are within maintenance schedule.</p>
          ) : (
            <ul className="space-y-2">
              {data.trucks_maintenance_overdue.map(tid => (
                <li key={tid} className="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-700">
                  <Truck size={14} />
                  {tid}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
