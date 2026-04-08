import { MessageSquare, Image, Video, Settings } from 'lucide-react'
import type { Page } from '../../types'

const NAV: { id: Page; icon: React.ElementType; label: string; color: string }[] = [
  { id: 'chat',     icon: MessageSquare, label: 'Chat',     color: '#a78bfa' },
  { id: 'image',    icon: Image,         label: 'Image',    color: '#f472b6' },
  { id: 'video',    icon: Video,         label: 'Video',    color: '#38bdf8' },
  { id: 'settings', icon: Settings,      label: 'Settings', color: '#94a3b8' },
]

interface Props {
  active: Page
  onChange: (p: Page) => void
}

export function Sidebar({ active, onChange }: Props) {
  return (
    <aside className="flex flex-col items-center w-14 shrink-0 py-4 gap-1"
      style={{ background: '#08080f', borderRight: '1px solid var(--border)' }}>

      {/* Logo mark */}
      <div className="w-8 h-8 rounded-xl mb-4 flex items-center justify-center text-xs font-black text-white"
        style={{ background: 'linear-gradient(135deg, #8b5cf6, #6366f1)' }}>
        F
      </div>

      {NAV.map(({ id, icon: Icon, label, color }) => {
        const isActive = active === id
        return (
          <button key={id} onClick={() => onChange(id)} title={label}
            className="relative group w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200"
            style={isActive
              ? { background: `${color}18`, boxShadow: `0 0 0 1px ${color}40` }
              : { background: 'transparent' }
            }>
            <Icon size={18} style={{ color: isActive ? color : '#4a4a6a' }} />

            {/* Tooltip */}
            <span className="pointer-events-none absolute left-full ml-3 px-2 py-1 rounded-md text-xs font-medium whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity z-50"
              style={{ background: '#1a1a2e', color: '#e2e2f0', border: '1px solid var(--border)' }}>
              {label}
            </span>
          </button>
        )
      })}
    </aside>
  )
}
