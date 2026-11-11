import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, CheckCircle, XCircle } from 'lucide-react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import RiskBadge from '../components/RiskBadge'
import Spinner from '../components/Spinner'

interface Props {
  shipmentId: string
  onBack: () => void
  onInvestigate: (id: string) => void
}

// Parse the evidence_summary text into timeline lines
function parseTimeline(summary: string): string[] {
  const start = summary.indexOf('--- TIMELINE')
  if (start === -1) return []
  return summary
    .slice(start)
    .split('\n')
    .filter(l => l.match(/^\d{4}-\d{2}-\d{2}T/) || l.includes('⚠') || l.includes('🔴') || l.includes('🚨'))
    .slice(0, 20)
}

// Extract excursion window lines
function parseExcursions(summary: string): string[] {
  const lines = summary.split('\n')
  return lines.filter(l => l.trim().startsWith('Window #'))
}

// Build a minimal sparkline from the evidence summary (window peak temps)
function buildChartData(summary: string, min: number, max: number) {
  const peaks: { label: string; temp: number }[] = []
  const matches = [...summary.matchAll(/peak=(-?[\d.]+)°C/g)]
  matches.forEach((m, i) => peaks.push({ label: `W${i + 1}`, temp: parseFloat(m[1]) }))
  if (peaks.length === 0) return []
  return [
    { label: 'Start', temp: (min + max) / 2 },
    ...peaks,
    { label: 'End', temp: (min + max) / 2 },
  ]
}

function extractRange(summary: string): [number, number] {
  const m = summary.match(/required: (-?[\d.]+)°C\s*–\s*(-?[\d.]+)°C/)
  return m ? [parseFloat(m[1]), parseFloat(m[2])] : [0, 10]
}

export default function ShipmentDetail({ shipmentId, onBack, onInvestigate }: Props) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['shipment', shipmentId],
    queryFn:  () => api.shipmentAnalysis(shipmentId),
  })

  if (isLoading) return <Spinner label={`Loading ${shipmentId}…`} />
  if (error || !data) return (
    <div className="py-16 text-center">
      <p className="text-red-500">Failed to load shipment data.</p>
      <button onClick={onBack} className="mt-4 text-sm text-blue-600 hover:underline">← Back</button>
    </div>
  )

  const [tMin, tMax] = extractRange(data.evidence_summary)
  const chartData     = buildChartData(data.evidence_summary, tMin, tMax)
  const timeline      = parseTimeline(data.evidence_summary)
  const excursions    = parseExcursions(data.evidence_summary)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900">
          <ArrowLeft size={16} /> Back
        </button>
        <h1 className="text-2xl font-bold text-gray-900 font-mono">{shipmentId}</h1>
        <RiskBadge level={data.risk_label} size="lg" />
        {data.is_compliant
          ? <span className="flex items-center gap-1 text-green-600 text-sm font-medium"><CheckCircle size={16} /> Compliant</span>
          : <span className="flex items-center gap-1 text-red-600 text-sm font-medium"><XCircle size={16} /> Non-compliant</span>
        }
        <button
          onClick={() => onInvestigate(shipmentId)}
          className="ml-auto rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
        >
          Investigate with AI
        </button>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: 'Risk Score', value: `${data.risk_score}/10` },
          { label: 'Excursion Windows', value: data.excursion_windows },
          { label: 'Total Readings', value: data.total_readings },
          { label: 'MKT', value: data.mkt_celsius != null ? `${data.mkt_celsius.toFixed(2)}°C` : 'N/A' },
        ].map(k => (
          <div key={k.label} className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm text-center">
            <p className="text-xs text-gray-500">{k.label}</p>
            <p className="mt-1 text-xl font-bold text-gray-900">{k.value}</p>
          </div>
        ))}
      </div>

      {/* Chart + excursions */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {chartData.length > 0 && (
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold text-gray-700">Excursion Peak Temperatures</h2>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} unit="°C" />
                <Tooltip formatter={(v: number) => [`${v}°C`, 'Temperature']} />
                <ReferenceLine y={tMin} stroke="#3b82f6" strokeDasharray="4 2" label={{ value: `Min ${tMin}°C`, position: 'right', fontSize: 10 }} />
                <ReferenceLine y={tMax} stroke="#ef4444" strokeDasharray="4 2" label={{ value: `Max ${tMax}°C`, position: 'right', fontSize: 10 }} />
                <Line type="monotone" dataKey="temp" stroke="#f97316" strokeWidth={2} dot={{ r: 4, fill: '#f97316' }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}

        {excursions.length > 0 && (
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-sm font-semibold text-gray-700">Excursion Windows</h2>
            <ul className="space-y-2">
              {excursions.map((line, i) => (
                <li key={i} className="rounded-lg bg-orange-50 px-3 py-2 text-xs font-mono text-orange-800">{line.trim()}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Correlations */}
      {data.correlations.length > 0 && (
        <div className="rounded-xl border border-orange-200 bg-orange-50 p-6 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold text-orange-800">Correlation Findings</h2>
          <div className="space-y-3">
            {data.correlations.map((c, i) => (
              <pre key={i} className="whitespace-pre-wrap rounded bg-white p-3 text-xs text-gray-700 shadow-sm border border-orange-100">{c}</pre>
            ))}
          </div>
        </div>
      )}

      {/* Timeline */}
      {timeline.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold text-gray-700">Key Timeline Events</h2>
          <ul className="space-y-1">
            {timeline.map((line, i) => (
              <li key={i} className="rounded px-2 py-1 font-mono text-xs text-gray-600 hover:bg-gray-50">{line}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
