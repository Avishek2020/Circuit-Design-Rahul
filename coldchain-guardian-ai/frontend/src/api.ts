import axios from 'axios'

const http = axios.create({ baseURL: '/api/v1' })

// ── types ──────────────────────────────────────────────────────────────────

export interface HealthStatus {
  status: string
  agent_mode: 'live' | 'mock'
  db_available: boolean
  version: string
}

export interface FleetSummary {
  total_shipments: number
  shipments_with_excursion: number
  shipments_with_incidents: number
  total_incidents: number
  total_financial_loss_usd: number
  regulatory_reportable_incidents: number
  status_breakdown: Record<string, number>
  trucks_maintenance_overdue: string[]
  total_trucks: number
}

export interface ProblemShipment {
  shipment_id: string
  status: string | null
  product_type: string | null
  truck_id: string | null
  excursion_readings: number
  incident_count: number
}

export interface ShipmentAnalysis {
  shipment_id: string
  risk_score: number
  risk_label: string
  excursion_windows: number
  is_compliant: boolean
  total_readings: number
  mkt_celsius: number | null
  correlations: string[]
  evidence_summary: string
}

export interface Finding {
  title: string
  detail: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  evidence: string[]
}

export interface InvestigationReport {
  query: string
  summary: string
  findings: Finding[]
  sop_citations: string[]
  recommended_actions: string[]
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  regulatory_reportable: boolean
  shipments_analyzed: string[]
  generated_at: string
}

// ── API calls ──────────────────────────────────────────────────────────────

export const api = {
  health: () =>
    http.get<HealthStatus>('/health').then(r => r.data),

  fleetSummary: () =>
    http.get<FleetSummary>('/fleet/summary').then(r => r.data),

  fleetProblems: (limit = 20, statusFilter?: string) =>
    http.get<ProblemShipment[]>('/fleet/problems', {
      params: { limit, ...(statusFilter ? { status_filter: statusFilter } : {}) },
    }).then(r => r.data),

  shipmentAnalysis: (id: string) =>
    http.get<ShipmentAnalysis>(`/shipments/${id}/analysis`).then(r => r.data),

  investigate: (query: string) =>
    http.post<InvestigationReport>('/investigate', { query }).then(r => r.data),
}
