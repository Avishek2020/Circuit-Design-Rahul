import { useQuery } from '@tanstack/react-query'
import { ChevronRight, Thermometer, AlertTriangle } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api'
import RiskBadge from '../components/RiskBadge'
import Spinner from '../components/Spinner'

const STATUS_LABEL: Record<string, string> = {
  failed_inspection: 'Failed Inspection',
  in_transit:        'In Transit',
  delivered:         'Delivered',
  delayed:           'Delayed',
  pending:           'Pending',
}

interface Props { onSelect: (id: string) => void }

export default function ProblemShipments({ onSelect }: Props) {
  const [statusFilter, setStatusFilter] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['fleetProblems', statusFilter],
    queryFn:  () => api.fleetProblems(30, statusFilter || undefined),
  })

  if (isLoading) return <Spinner label="Loading problem shipments…" />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Problem Shipments</h1>
          <p className="mt-1 text-sm text-gray-500">Shipments with temperature excursions or incidents</p>
        </div>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All statuses</option>
          {Object.entries(STATUS_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr>
              {['Shipment', 'Product', 'Truck', 'Status', 'Excursions', 'Incidents', ''].map(h => (
                <th key={h} className="px-4 py-3 text-left font-semibold text-gray-600">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {(data ?? []).map(s => (
              <tr
                key={s.shipment_id}
                onClick={() => onSelect(s.shipment_id)}
                className="cursor-pointer hover:bg-blue-50 transition-colors"
              >
                <td className="px-4 py-3 font-mono font-semibold text-blue-700">{s.shipment_id}</td>
                <td className="px-4 py-3 text-gray-700">{s.product_type ?? '—'}</td>
                <td className="px-4 py-3 font-mono text-gray-500">{s.truck_id ?? '—'}</td>
                <td className="px-4 py-3">
                  <RiskBadge level={s.status === 'failed_inspection' ? 'HIGH' : s.status === 'delayed' ? 'MEDIUM' : 'LOW'} size="sm" />
                  <span className="ml-2 text-gray-500">{STATUS_LABEL[s.status ?? ''] ?? s.status}</span>
                </td>
                <td className="px-4 py-3">
                  {s.excursion_readings > 0 && (
                    <span className="inline-flex items-center gap-1 text-orange-600 font-medium">
                      <Thermometer size={13} /> {s.excursion_readings}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  {s.incident_count > 0 && (
                    <span className="inline-flex items-center gap-1 text-red-600 font-medium">
                      <AlertTriangle size={13} /> {s.incident_count}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-400"><ChevronRight size={16} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        {!data?.length && (
          <p className="py-10 text-center text-sm text-gray-400">No problem shipments found.</p>
        )}
      </div>
    </div>
  )
}
