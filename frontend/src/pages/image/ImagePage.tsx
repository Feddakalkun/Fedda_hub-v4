import { useState, useEffect, useRef } from "react"
import { Image, Download, Loader2, Wifi, WifiOff, Sliders } from "lucide-react"

const STEPS_MIN = 1
const STEPS_MAX = 50
const SIZE_OPTIONS = [512, 768, 1024]

export function ImagePage() {
  const [prompt, setPrompt]       = useState("")
  const [negative, setNegative]   = useState("")
  const [steps, setSteps]         = useState(20)
  const [width, setWidth]         = useState(512)
  const [height, setHeight]       = useState(512)
  const [loading, setLoading]     = useState(false)
  const [imageUrl, setImageUrl]   = useState<string | null>(null)
  const [error, setError]         = useState<string | null>(null)
  const [online, setOnline]       = useState<boolean | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Poll ComfyUI status every 5 s
  useEffect(() => {
    const check = async () => {
      try {
        const r = await fetch("/api/comfy/status")
        const d = await r.json()
        setOnline(d.online === true)
      } catch {
        setOnline(false)
      }
    }
    check()
    pollRef.current = setInterval(check, 5000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const handleGenerate = async () => {
    if (!prompt.trim()) return
    setLoading(true)
    setError(null)
    setImageUrl(null)
    try {
      const r = await fetch("/api/comfy/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, negative, steps, width, height, model: "" }),
      })
      if (!r.ok) {
        const t = await r.text()
        throw new Error(`Server error ${r.status}: ${t.slice(0, 200)}`)
      }
      const d = await r.json()
      setImageUrl(d.image_url ? `/api${d.image_url}` : null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = () => {
    if (!imageUrl) return
    const a = document.createElement("a")
    a.href = imageUrl
    a.download = "fedda-generated.png"
    a.click()
  }

  return (
    <div className="flex h-full overflow-hidden" style={{ background: "var(--bg)" }}>
      {/* ── Left panel ────────────────────────────────────────────────── */}
      <aside
        className="flex flex-col gap-4 p-5 overflow-y-auto shrink-0"
        style={{ width: 320, borderRight: "1px solid var(--border)", background: "#0c0c18" }}
      >
        {/* Header + status */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Image size={18} className="text-pink-400" />
            <span className="font-semibold text-sm text-white">Image Studio</span>
          </div>
          <StatusBadge online={online} />
        </div>

        {/* Prompt */}
        <label className="flex flex-col gap-1">
          <span className="text-xs text-white/50 uppercase tracking-wide">Prompt</span>
          <textarea
            rows={4}
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            placeholder="a futuristic city at night, neon lights, cinematic..."
            className="resize-none rounded-xl p-3 text-sm text-white/90 outline-none placeholder:text-white/20 transition"
            style={{ background: "#14141f", border: "1px solid var(--border)" }}
          />
        </label>

        {/* Negative prompt */}
        <label className="flex flex-col gap-1">
          <span className="text-xs text-white/50 uppercase tracking-wide">Negative Prompt</span>
          <textarea
            rows={2}
            value={negative}
            onChange={e => setNegative(e.target.value)}
            placeholder="blurry, low quality, watermark..."
            className="resize-none rounded-xl p-3 text-sm text-white/60 outline-none placeholder:text-white/20 transition"
            style={{ background: "#14141f", border: "1px solid var(--border)" }}
          />
        </label>

        {/* Steps slider */}
        <label className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1 text-xs text-white/50 uppercase tracking-wide">
              <Sliders size={12} /> Steps
            </span>
            <span className="text-xs font-mono text-violet-300">{steps}</span>
          </div>
          <input
            type="range"
            min={STEPS_MIN}
            max={STEPS_MAX}
            value={steps}
            onChange={e => setSteps(Number(e.target.value))}
            className="accent-violet-500 w-full"
          />
        </label>

        {/* Width / Height */}
        <div className="flex gap-3">
          <label className="flex flex-col gap-1 flex-1">
            <span className="text-xs text-white/50 uppercase tracking-wide">Width</span>
            <select
              value={width}
              onChange={e => setWidth(Number(e.target.value))}
              className="rounded-xl px-3 py-2 text-sm text-white/90 outline-none"
              style={{ background: "#14141f", border: "1px solid var(--border)" }}
            >
              {SIZE_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 flex-1">
            <span className="text-xs text-white/50 uppercase tracking-wide">Height</span>
            <select
              value={height}
              onChange={e => setHeight(Number(e.target.value))}
              className="rounded-xl px-3 py-2 text-sm text-white/90 outline-none"
              style={{ background: "#14141f", border: "1px solid var(--border)" }}
            >
              {SIZE_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
        </div>

        {/* Generate button */}
        <button
          onClick={handleGenerate}
          disabled={loading || !prompt.trim()}
          className="mt-auto flex items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold transition-all disabled:opacity-40"
          style={{
            background: loading ? "#2d1a4a" : "linear-gradient(135deg, #8b5cf6, #6366f1)",
            color: "#fff",
          }}
        >
          {loading ? <><Loader2 size={16} className="animate-spin" /> Generating…</> : "✦ Generate"}
        </button>
      </aside>

      {/* ── Right panel ───────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col items-center justify-center p-8 overflow-auto gap-4">
        {online === false && !loading && !imageUrl && (
          <OfflineBanner />
        )}

        {error && (
          <div className="w-full max-w-lg rounded-xl p-4 text-sm text-red-300"
            style={{ background: "#1f0a0a", border: "1px solid #7f1d1d" }}>
            {error}
          </div>
        )}

        {loading && (
          <div className="flex flex-col items-center gap-3 text-white/40">
            <Loader2 size={40} className="animate-spin text-violet-400" />
            <span className="text-sm">Generating image…</span>
          </div>
        )}

        {imageUrl && !loading && (
          <div className="flex flex-col items-center gap-3">
            <img
              src={imageUrl}
              alt="Generated"
              className="rounded-2xl max-w-full max-h-[70vh] shadow-2xl"
              style={{ border: "1px solid var(--border)" }}
            />
            <button
              onClick={handleDownload}
              className="flex items-center gap-2 rounded-xl px-5 py-2 text-sm font-medium transition"
              style={{ background: "#1a1a2e", border: "1px solid var(--border)", color: "#a78bfa" }}
            >
              <Download size={15} /> Download
            </button>
          </div>
        )}

        {!imageUrl && !loading && !error && online !== false && (
          <div className="flex flex-col items-center gap-3 opacity-30 select-none">
            <div className="w-20 h-20 rounded-3xl flex items-center justify-center"
              style={{ background: "rgba(244,114,182,0.08)", border: "1px solid rgba(244,114,182,0.15)" }}>
              <Image size={32} className="text-pink-400" />
            </div>
            <p className="text-sm text-white/40">Your generated image will appear here</p>
          </div>
        )}
      </main>
    </div>
  )
}

function StatusBadge({ online }: { online: boolean | null }) {
  if (online === null) return <span className="text-xs text-white/30">Checking…</span>
  return (
    <span
      className="flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium"
      style={online
        ? { background: "rgba(34,197,94,0.12)", color: "#4ade80", border: "1px solid rgba(34,197,94,0.25)" }
        : { background: "rgba(239,68,68,0.12)", color: "#f87171", border: "1px solid rgba(239,68,68,0.25)" }
      }
    >
      {online ? <Wifi size={11} /> : <WifiOff size={11} />}
      ComfyUI {online ? "Online" : "Offline"}
    </span>
  )
}

function OfflineBanner() {
  return (
    <div className="w-full max-w-md rounded-2xl p-5 text-center"
      style={{ background: "#120c1e", border: "1px solid rgba(139,92,246,0.2)" }}>
      <WifiOff size={28} className="text-violet-400 mx-auto mb-3" />
      <p className="text-white/70 font-medium text-sm">ComfyUI is not running</p>
      <p className="text-white/35 text-xs mt-1">
        Start ComfyUI on port <code className="text-violet-300">8188</code> to enable image generation.
      </p>
    </div>
  )
}
