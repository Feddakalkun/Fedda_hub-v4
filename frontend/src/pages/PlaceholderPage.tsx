import { Image, Video, Settings } from 'lucide-react'

const pages = [
  { icon: Image,    label: 'Image Studio',   desc: 'Text-to-image, img2img — coming soon' },
  { icon: Video,    label: 'Video Studio',    desc: 'LTX, WAN 2.2 — coming soon' },
  { icon: Settings, label: 'Settings',        desc: 'Backend config — coming soon' },
] as const

export function PlaceholderPage({ title }: { title: string }) {
  const page = pages.find(p => p.label.toLowerCase().startsWith(title.toLowerCase()))
  const Icon = page?.icon ?? Settings
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 opacity-40 select-none">
      <div className="w-14 h-14 rounded-2xl flex items-center justify-center"
        style={{ background: 'rgba(139,92,246,0.1)', border: '1px solid rgba(139,92,246,0.2)' }}>
        <Icon size={24} className="text-violet-400" />
      </div>
      <div className="text-center">
        <p className="font-semibold text-white/60">{page?.label ?? title}</p>
        <p className="text-xs text-white/30 mt-1">{page?.desc ?? 'Coming soon'}</p>
      </div>
    </div>
  )
}
