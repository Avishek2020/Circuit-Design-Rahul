interface Props {
  level: string
  size?: 'sm' | 'md' | 'lg'
}

const colours: Record<string, string> = {
  LOW:      'bg-green-100 text-green-800 ring-green-300',
  MEDIUM:   'bg-yellow-100 text-yellow-800 ring-yellow-300',
  HIGH:     'bg-orange-100 text-orange-800 ring-orange-300',
  CRITICAL: 'bg-red-100 text-red-800 ring-red-300',
  low:      'bg-green-100 text-green-800 ring-green-300',
  medium:   'bg-yellow-100 text-yellow-800 ring-yellow-300',
  high:     'bg-orange-100 text-orange-800 ring-orange-300',
  critical: 'bg-red-100 text-red-800 ring-red-300',
}

const sizes = { sm: 'px-2 py-0.5 text-xs', md: 'px-2.5 py-1 text-sm', lg: 'px-3 py-1.5 text-base' }

export default function RiskBadge({ level, size = 'md' }: Props) {
  const cls = colours[level] ?? 'bg-gray-100 text-gray-700 ring-gray-300'
  return (
    <span className={`inline-flex items-center rounded-full font-semibold ring-1 ring-inset ${cls} ${sizes[size]}`}>
      {level.toUpperCase()}
    </span>
  )
}
