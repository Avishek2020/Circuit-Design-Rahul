import { useMutation } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle, Loader2, Search, Shield } from 'lucide-react'
import { useState } from 'react'
import { api, type InvestigationReport } from '../api'
import RiskBadge from '../components/RiskBadge'

const SAMPLE_QUERIES = [
  'Give me a fleet overview of all problem shipments',
  'Investigate the worst temperature excursion this week',
  'Which trucks have recurring incidents?',
]

const SEV_ICON: Record<string, string> = {
  low: '🟢', medium: '🟡', high: '🔴', critical: '🚨',
}

function ReportView({ report }: { report: InvestigationReport }) {
  return (
    <div className="space-y-6 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
      {/* Header */}
      <div className="flex flex-wrap items-start gap-3 border-b border-gray-100 pb-4">
        <div className="flex-1">
          <p className="text-xs text-gray-400">Query</p>
          <p className="mt-0.5 text-sm font-medium text-gray-700 italic">"{report.query}"</p>
        </div>
        <RiskBadge level={report.risk_level} size="lg" />
        {report.regulatory_reportable && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-red-100 px-3 py-1 text-sm font-semibold text-red-700 ring-1 ring-inset ring-red-300">
            <AlertTriangle size={13} /> Regulatory Reportable
          </span>
        )}
      </div>

      {/* Summary */}
      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">Executive Summary</h3>
        <p className="text-sm leading-relaxed text-gray-700">{report.summary}</p>
      </div>

      {/* Findings */}
      {report.findings.length > 0 && (
        <div>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-400">Findings ({report.findings.length})</h3>
          <div className="space-y-3">
            {report.findings.map((f, i) => (
              <div key={i} className="rounded-lg border border-gray-100 bg-gray-50 p-4">
                <div className="flex items-start justify-between gap-2">
                  <p className="font-semibold text-gray-800 text-sm">
                    {SEV_ICON[f.severity] ?? '·'} {f.title}
                  </p>
                  <RiskBadge level={f.severity} size="sm" />
                </div>
                <p className="mt-1.5 text-sm text-gray-600">{f.detail}</p>
                {f.evidence.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {f.evidence.map((ev, j) => (
                      <li key={j} className="text-xs text-gray-500">• {ev}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SOP Citations */}
      {report.sop_citations.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">SOP Citations</h3>
          <ul className="space-y-1">
            {report.sop_citations.map((c, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-blue-700">
                <Shield size={12} className="shrink-0" /> {c}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Recommended Actions */}
      {report.recommended_actions.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-400">Recommended Actions</h3>
          <ol className="space-y-1.5 list-decimal list-inside">
            {report.recommended_actions.map((a, i) => (
              <li key={i} className="text-sm text-gray-700">{a}</li>
            ))}
          </ol>
        </div>
      )}

      {/* Footer */}
      <div className="flex flex-wrap gap-4 border-t border-gray-100 pt-3 text-xs text-gray-400">
        {report.shipments_analyzed.length > 0 && (
          <span>Shipments: {report.shipments_analyzed.join(', ')}</span>
        )}
        <span>Generated: {new Date(report.generated_at).toLocaleString()}</span>
      </div>
    </div>
  )
}

interface Props { initialQuery?: string }

export default function Investigation({ initialQuery = '' }: Props) {
  const [query, setQuery] = useState(initialQuery)

  const { mutate, data, isPending, error } = useMutation({
    mutationFn: api.investigate,
  })

  // Auto-run if initialQuery is set (pre-filled from shipment detail)
  const hasAutoRun = initialQuery && data?.query === initialQuery

  const submit = (q = query) => {
    if (q.trim().length < 5) return
    setQuery(q)
    mutate(q)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">AI Investigation Agent</h1>
        <p className="mt-1 text-sm text-gray-500">
          Ask a natural-language question — the agent analyses temperature data, maintenance records, and SOPs.
        </p>
      </div>

      {/* Query box */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <label className="block text-sm font-medium text-gray-700 mb-2">Investigation Query</label>
        <div className="flex gap-3">
          <textarea
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && e.metaKey) submit() }}
            placeholder="e.g. What caused the temperature excursion on shipment SHP-0007?"
            rows={3}
            className="flex-1 resize-none rounded-lg border border-gray-300 px-4 py-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder:text-gray-400"
          />
          <button
            onClick={() => submit()}
            disabled={isPending || query.trim().length < 5}
            className="flex items-center gap-2 self-start rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {isPending ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
            Investigate
          </button>
        </div>
        <p className="mt-1.5 text-xs text-gray-400">Tip: ⌘+Enter to submit</p>

        {/* Sample queries */}
        <div className="mt-4 flex flex-wrap gap-2">
          {SAMPLE_QUERIES.map(q => (
            <button
              key={q}
              onClick={() => submit(q)}
              className="rounded-full border border-gray-300 bg-gray-50 px-3 py-1 text-xs text-gray-600 hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Loading */}
      {isPending && (
        <div className="flex items-center justify-center gap-3 rounded-xl border border-blue-100 bg-blue-50 py-10">
          <Loader2 size={20} className="animate-spin text-blue-500" />
          <p className="text-sm text-blue-700 font-medium">Agent is investigating…</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Investigation failed: {(error as Error).message}
        </div>
      )}

      {/* Success */}
      {data && !isPending && <ReportView report={data} />}

      {/* Empty state */}
      {!data && !isPending && !error && (
        <div className="flex flex-col items-center gap-3 py-16 text-gray-300">
          <CheckCircle size={48} />
          <p className="text-sm">Submit a query to start the investigation</p>
        </div>
      )}
    </div>
  )
}
