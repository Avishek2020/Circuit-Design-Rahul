import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { ActivitySquare, LayoutDashboard, Search, Thermometer } from 'lucide-react'
import { useState } from 'react'
import { api } from './api'
import FleetDashboard from './pages/FleetDashboard'
import Investigation from './pages/Investigation'
import ProblemShipments from './pages/ProblemShipments'
import ShipmentDetail from './pages/ShipmentDetail'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } })

type Page = 'dashboard' | 'problems' | 'detail' | 'investigate'

function NavItem({ icon, label, active, onClick }: {
  icon: React.ReactNode; label: string; active: boolean; onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2.5 w-full rounded-lg px-3 py-2.5 text-sm font-medium transition-colors
        ${active ? 'bg-blue-700 text-white' : 'text-blue-100 hover:bg-blue-700/60'}`}
    >
      {icon} {label}
    </button>
  )
}

function StatusDot() {
  const { data } = useQuery({ queryKey: ['health'], queryFn: api.health, staleTime: 60_000 })
  if (!data) return null
  return (
    <div className="flex items-center gap-1.5 text-xs text-blue-200">
      <span className={`h-2 w-2 rounded-full ${data.agent_mode === 'live' ? 'bg-green-400' : 'bg-yellow-400'}`} />
      Agent: {data.agent_mode} · DB: {data.db_available ? 'connected' : 'offline'}
    </div>
  )
}

function Shell() {
  const [page, setPage]             = useState<Page>('dashboard')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [investQuery, setInvestQuery] = useState('')

  const goDetail = (id: string) => { setSelectedId(id); setPage('detail') }
  const goInvestigate = (prefill: string) => {
    setInvestQuery(`Full investigation of shipment ${prefill}`)
    setPage('investigate')
  }

  const nav = [
    { id: 'dashboard'   as Page, icon: <LayoutDashboard size={16} />, label: 'Fleet Dashboard'   },
    { id: 'problems'    as Page, icon: <Thermometer     size={16} />, label: 'Problem Shipments' },
    { id: 'investigate' as Page, icon: <Search          size={16} />, label: 'AI Investigation'  },
  ]

  return (
    <div className="flex h-screen bg-gray-100 overflow-hidden">
      {/* Sidebar */}
      <aside className="flex w-56 shrink-0 flex-col bg-blue-800 text-white">
        <div className="border-b border-blue-700 px-4 py-5">
          <div className="flex items-center gap-2">
            <ActivitySquare size={20} className="text-blue-300" />
            <span className="font-bold tracking-tight text-sm leading-tight">
              ColdChain<br />Guardian AI
            </span>
          </div>
          <div className="mt-3"><StatusDot /></div>
        </div>

        <nav className="flex-1 space-y-1 p-3">
          {nav.map(n => (
            <NavItem
              key={n.id}
              icon={n.icon}
              label={n.label}
              active={page === n.id || (page === 'detail' && n.id === 'problems')}
              onClick={() => { setPage(n.id); if (n.id !== 'detail') setSelectedId(null) }}
            />
          ))}
        </nav>

        <div className="border-t border-blue-700 p-4 text-xs text-blue-300">
          <p className="font-medium text-blue-100">Day 6 — Dashboard</p>
          <p className="mt-0.5">React + FastAPI</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="mx-auto max-w-6xl p-8">
          {page === 'dashboard'   && <FleetDashboard />}
          {page === 'problems'    && <ProblemShipments onSelect={goDetail} />}
          {page === 'detail'      && selectedId && (
            <ShipmentDetail
              shipmentId={selectedId}
              onBack={() => setPage('problems')}
              onInvestigate={goInvestigate}
            />
          )}
          {page === 'investigate' && <Investigation initialQuery={investQuery} />}
        </div>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <Shell />
    </QueryClientProvider>
  )
}
