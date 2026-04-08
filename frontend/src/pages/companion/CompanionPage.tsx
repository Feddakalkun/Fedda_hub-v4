import { useCallback, useEffect, useRef, useState } from "react"
import { Send, StopCircle, Brain, Trash2, Pin, ChevronDown, X, Plus, ChevronRight } from "lucide-react"
import ReactMarkdown from "react-markdown"
import { useOllamaModels } from "../../hooks/useOllamaModels"

function uid() { return Math.random().toString(36).slice(2) }

// ── Types ─────────────────────────────────────────────────────────────────────

interface Avatar {
  id: string
  name: string
  emoji: string
  tagline: string
  color: string
  gradient: string
  bg: string
  border: string
}

interface Memory {
  memory_id: string
  content: string
  tags: string[]
  pinned: boolean
  created_at: string
}

interface CompanionMessage {
  id: string
  role: "user" | "assistant"
  content: string
}

// ── Avatar picker ─────────────────────────────────────────────────────────────

function AvatarPicker({ onSelect }: { onSelect: (a: Avatar) => void }) {
  const [avatars, setAvatars] = useState<Avatar[]>([])

  useEffect(() => {
    fetch("/api/companion/avatars").then(r => r.json()).then(setAvatars).catch(() => {})
  }, [])

  return (
    <div className="flex flex-col items-center justify-center h-full gap-8 px-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-white/90 mb-2">Choose your Co-Partner</h2>
        <p className="text-sm text-white/40">Each partner has their own personality and remembers everything you share</p>
      </div>
      <div className="grid grid-cols-2 gap-4 w-full max-w-lg">
        {avatars.map(a => (
          <button key={a.id} onClick={() => onSelect(a)}
            className="group relative flex flex-col items-center gap-3 rounded-2xl p-6 transition-all duration-200 hover:scale-[1.02]"
            style={{ background: a.bg, border: `1px solid ${a.border}` }}>
            <div className="w-16 h-16 rounded-full flex items-center justify-center text-3xl"
              style={{ background: a.gradient, boxShadow: `0 8px 24px ${a.color}40` }}>
              {a.emoji}
            </div>
            <div className="text-center">
              <div className="font-bold text-white/90 text-lg">{a.name}</div>
              <div className="text-xs text-white/40 mt-1">{a.tagline}</div>
            </div>
            <div className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity"
              style={{ boxShadow: `0 0 0 2px ${a.color}60` }} />
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Memory panel ──────────────────────────────────────────────────────────────

function MemoryPanel({
  avatar, memories, onForget, onForgetAll, onAdd, onClose,
}: {
  avatar: Avatar
  memories: Memory[]
  onForget: (id: string) => void
  onForgetAll: () => void
  onAdd: (content: string) => void
  onClose: () => void
}) {
  const [newMem, setNewMem] = useState("")

  const submit = () => {
    const t = newMem.trim()
    if (t) { onAdd(t); setNewMem("") }
  }

  const pinned = memories.filter(m => m.pinned)
  const regular = memories.filter(m => !m.pinned)

  return (
    <div className="flex flex-col h-full w-72 shrink-0" style={{ borderLeft: "1px solid var(--border)", background: "#09090f" }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 h-12 shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="flex items-center gap-2">
          <Brain size={14} style={{ color: avatar.color }} />
          <span className="text-xs font-semibold text-white/70">{avatar.name}'s Memory</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
            style={{ background: avatar.bg, color: avatar.color, border: `1px solid ${avatar.border}` }}>
            {memories.length}
          </span>
        </div>
        <button onClick={onClose} className="text-white/20 hover:text-white/60 transition-colors"><X size={14} /></button>
      </div>

      {/* Add memory */}
      <div className="px-3 py-3 shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="flex gap-2">
          <input
            value={newMem}
            onChange={e => setNewMem(e.target.value)}
            onKeyDown={e => e.key === "Enter" && submit()}
            placeholder="Remember something…"
            className="flex-1 bg-transparent text-xs text-white/70 placeholder:text-white/20 outline-none px-3 py-1.5 rounded-lg"
            style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}
          />
          <button onClick={submit} className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 transition-colors"
            style={{ background: avatar.bg, border: `1px solid ${avatar.border}` }}>
            <Plus size={12} style={{ color: avatar.color }} />
          </button>
        </div>
      </div>

      {/* Memory list */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
        {memories.length === 0 && (
          <p className="text-[10px] text-white/20 text-center py-8">No memories yet</p>
        )}
        {pinned.length > 0 && (
          <>
            <p className="text-[9px] text-white/20 uppercase tracking-widest px-1 flex items-center gap-1">
              <Pin size={8} /> Pinned
            </p>
            {pinned.map(m => <MemoryCard key={m.memory_id} m={m} avatar={avatar} onForget={onForget} />)}
          </>
        )}
        {regular.length > 0 && (
          <>
            {pinned.length > 0 && <p className="text-[9px] text-white/20 uppercase tracking-widest px-1 mt-2">Recent</p>}
            {regular.map(m => <MemoryCard key={m.memory_id} m={m} avatar={avatar} onForget={onForget} />)}
          </>
        )}
      </div>

      {/* Footer */}
      {memories.length > 0 && (
        <div className="px-3 py-3 shrink-0" style={{ borderTop: "1px solid var(--border)" }}>
          <button onClick={onForgetAll}
            className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[10px] text-red-400/50 hover:text-red-400/80 transition-colors"
            style={{ border: "1px solid rgba(248,113,113,0.1)" }}>
            <Trash2 size={10} /> Forget everything
          </button>
        </div>
      )}
    </div>
  )
}

function MemoryCard({ m, avatar, onForget }: { m: Memory; avatar: Avatar; onForget: (id: string) => void }) {
  return (
    <div className="group flex items-start gap-2 rounded-xl px-3 py-2 transition-colors"
      style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
      {m.pinned && <Pin size={9} className="mt-0.5 shrink-0" style={{ color: avatar.color }} />}
      <span className="flex-1 text-[11px] text-white/60 leading-relaxed">{m.content}</span>
      <button onClick={() => onForget(m.memory_id)}
        className="opacity-0 group-hover:opacity-100 transition-opacity text-red-400/50 hover:text-red-400/80 shrink-0">
        <X size={11} />
      </button>
    </div>
  )
}

// ── Chat message ──────────────────────────────────────────────────────────────

function CompanionMessage({
  msg, avatar, streaming,
}: {
  msg: CompanionMessage
  avatar: Avatar
  streaming: boolean
}) {
  const isUser = msg.role === "user"
  // Hide auto-remember lines from display
  const displayContent = msg.content
    .split("\n")
    .filter(l => !l.trim().toUpperCase().startsWith("REMEMBER:"))
    .join("\n")
    .trim()

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      <div className="w-8 h-8 rounded-full shrink-0 flex items-center justify-center text-sm font-bold"
        style={isUser
          ? { background: "linear-gradient(135deg, #6366f1, #8b5cf6)", color: "#fff" }
          : { background: avatar.gradient, boxShadow: `0 4px 12px ${avatar.color}40` }
        }>
        {isUser ? "U" : avatar.emoji}
      </div>
      <div className={`max-w-[75%] ${isUser ? "items-end" : "items-start"} flex flex-col`}>
        {(displayContent || (streaming && !isUser)) && (
          <div className="rounded-2xl px-4 py-2.5 text-sm leading-relaxed prose prose-invert max-w-none"
            style={isUser
              ? { background: "linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.15))", border: "1px solid rgba(139,92,246,0.2)", color: "#e2e2f0" }
              : { background: "var(--bg-surface)", border: `1px solid ${avatar.border}`, color: "#c4c4d8" }
            }>
            {msg.role === "assistant"
              ? <ReactMarkdown>{displayContent || (streaming ? "▌" : "")}</ReactMarkdown>
              : displayContent}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function CompanionPage() {
  const { models, online } = useOllamaModels()
  const [model, setModel] = useState("")
  const [avatar, setAvatar] = useState<Avatar | null>(() => {
    try { return JSON.parse(localStorage.getItem("companion_avatar") || "null") } catch { return null }
  })
  const [messages, setMessages] = useState<CompanionMessage[]>([])
  const [memories, setMemories] = useState<Memory[]>([])
  const [showMemory, setShowMemory] = useState(false)
  const [input, setInput] = useState("")
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const [newMemFlash, setNewMemFlash] = useState(false)

  useEffect(() => { if (!model && models.length) setModel(models[0]) }, [models, model])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }) }, [messages])

  useEffect(() => {
    if (!avatar) return
    localStorage.setItem("companion_avatar", JSON.stringify(avatar))
    fetch(`/api/companion/memories/${avatar.id}`)
      .then(r => r.json()).then(setMemories).catch(() => {})
  }, [avatar])

  const loadMemories = useCallback(() => {
    if (!avatar) return
    fetch(`/api/companion/memories/${avatar.id}`)
      .then(r => r.json()).then(setMemories).catch(() => {})
  }, [avatar])

  const addMemory = useCallback(async (content: string) => {
    if (!avatar) return
    const res = await fetch(`/api/companion/memories/${avatar.id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, tags: ["manual"] }),
    })
    const mem = await res.json()
    setMemories(prev => [mem, ...prev])
    setNewMemFlash(true)
    setTimeout(() => setNewMemFlash(false), 1500)
  }, [avatar])

  const forgetMemory = useCallback(async (memory_id: string) => {
    if (!avatar) return
    await fetch(`/api/companion/memories/${avatar.id}/${memory_id}`, { method: "DELETE" })
    setMemories(prev => prev.filter(m => m.memory_id !== memory_id))
  }, [avatar])

  const forgetAll = useCallback(async () => {
    if (!avatar || !confirm(`Forget everything ${avatar.name} knows? This cannot be undone.`)) return
    await fetch(`/api/companion/memories/${avatar.id}`, { method: "DELETE" })
    setMemories([])
  }, [avatar])

  const send = useCallback(async () => {
    const text = input.trim()
    if (!text || !model || !avatar || streaming) return

    const userMsg: CompanionMessage = { id: uid(), role: "user", content: text }
    const assistantId = uid()
    setMessages(prev => [
      ...prev,
      userMsg,
      { id: assistantId, role: "assistant", content: "" },
    ])
    setInput("")
    setStreaming(true)

    const ctrl = new AbortController()
    abortRef.current = ctrl

    try {
      const history = [...messages, userMsg].map(m => ({ role: m.role, content: m.content }))
      const res = await fetch("/api/companion/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ avatar_id: avatar.id, model, messages: history }),
        signal: ctrl.signal,
      })
      if (!res.ok) throw new Error(`Backend error ${res.status}`)

      const reader = res.body!.getReader()
      const dec = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = dec.decode(value, { stream: true })
        for (const line of chunk.split("\n")) {
          if (!line.startsWith("data: ")) continue
          try {
            const ev = JSON.parse(line.slice(6))
            if (ev.type === "token") {
              setMessages(prev => prev.map(m =>
                m.id === assistantId ? { ...m, content: m.content + ev.content } : m
              ))
            } else if (ev.type === "memories_added") {
              setMemories(prev => [...(ev.memories as Memory[]), ...prev])
              setNewMemFlash(true)
              setTimeout(() => setNewMemFlash(false), 1500)
            }
          } catch { /* partial */ }
        }
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name !== "AbortError") {
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: "⚠️ " + e.message } : m
        ))
      }
    } finally {
      setStreaming(false)
      abortRef.current = null
    }
  }, [input, model, avatar, messages, streaming])

  const stop = () => abortRef.current?.abort()
  const clear = () => { if (!streaming) setMessages([]) }
  const switchAvatar = () => {
    if (!streaming) {
      setAvatar(null)
      setMessages([])
      localStorage.removeItem("companion_avatar")
    }
  }

  if (!avatar) return <AvatarPicker onSelect={setAvatar} />

  return (
    <div className="flex h-full">
      {/* Chat area */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 h-12 shrink-0"
          style={{ borderBottom: "1px solid var(--border)" }}>
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-full flex items-center justify-center text-sm"
              style={{ background: avatar.gradient }}>
              {avatar.emoji}
            </div>
            <span className="text-sm font-semibold text-white/80">{avatar.name}</span>
            <span className="text-[10px] text-white/30">{avatar.tagline}</span>
          </div>
          <div className="flex items-center gap-2">
            {models.length > 0 && (
              <div className="relative">
                <select value={model} onChange={e => setModel(e.target.value)}
                  className="appearance-none pl-3 pr-7 py-1 rounded-lg text-xs font-medium text-white/70 outline-none cursor-pointer"
                  style={{ background: "var(--bg-input)", border: "1px solid var(--border)" }}>
                  {models.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
                <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-white/30" />
              </div>
            )}
            <button onClick={clear} disabled={streaming || messages.length === 0}
              className="px-2.5 py-1 rounded-lg text-[10px] uppercase tracking-widest text-white/30 hover:text-white/60 disabled:opacity-30 transition-colors"
              style={{ background: "var(--bg-input)" }}>
              Clear
            </button>
            <button onClick={switchAvatar} disabled={streaming}
              className="px-2.5 py-1 rounded-lg text-[10px] uppercase tracking-widest text-white/30 hover:text-white/60 disabled:opacity-30 transition-colors"
              style={{ background: "var(--bg-input)" }}>
              Switch
            </button>
            <button
              onClick={() => { setShowMemory(v => !v); loadMemories() }}
              className="relative flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] uppercase tracking-widest transition-colors"
              style={showMemory
                ? { background: avatar.bg, color: avatar.color, border: `1px solid ${avatar.border}` }
                : { background: "var(--bg-input)", color: "#ffffff50", border: "1px solid var(--border)" }
              }>
              <Brain size={11} />
              Memory
              {memories.length > 0 && (
                <span className="text-[9px] px-1 rounded-full font-bold"
                  style={{ background: avatar.color, color: "#000" }}>
                  {memories.length}
                </span>
              )}
              {newMemFlash && (
                <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full animate-ping"
                  style={{ background: avatar.color }} />
              )}
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-5">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-5 opacity-40 select-none">
              <div className="w-20 h-20 rounded-full flex items-center justify-center text-4xl"
                style={{ background: avatar.gradient, boxShadow: `0 12px 40px ${avatar.color}50` }}>
                {avatar.emoji}
              </div>
              <div className="text-center">
                <p className="text-base font-semibold text-white/70">Hey, I'm {avatar.name}</p>
                <p className="text-sm text-white/30 mt-1">{avatar.tagline}</p>
              </div>
            </div>
          )}
          {messages.map(msg => (
            <CompanionMessage key={msg.id} msg={msg} avatar={avatar} streaming={streaming && msg.role === "assistant" && msg === messages[messages.length - 1]} />
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="px-4 pb-4 shrink-0">
          <div className="flex items-end gap-2 rounded-2xl p-3"
            style={{ background: "var(--bg-surface)", border: `1px solid ${avatar.border}` }}>
            <textarea rows={1} value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send() } }}
              placeholder={online ? `Talk to ${avatar.name}…` : "Ollama offline"}
              disabled={!online || streaming}
              className="flex-1 resize-none bg-transparent text-sm text-white/80 placeholder:text-white/20 outline-none max-h-40 disabled:opacity-40"
            />
            <button onClick={streaming ? stop : send}
              disabled={!online || (!streaming && !input.trim())}
              className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0 transition-all duration-200 disabled:opacity-20"
              style={streaming
                ? { background: "rgba(248,113,113,0.15)", border: "1px solid rgba(248,113,113,0.3)", color: "#f87171" }
                : { background: avatar.gradient, color: "#fff" }
              }>
              {streaming ? <StopCircle size={15} /> : <Send size={15} />}
            </button>
          </div>
          <p className="text-center text-[9px] text-white/10 mt-1.5 tracking-widest uppercase">
            {avatar.name} remembers what matters · Open Memory panel to view or edit
          </p>
        </div>
      </div>

      {/* Memory panel */}
      {showMemory && (
        <MemoryPanel
          avatar={avatar}
          memories={memories}
          onForget={forgetMemory}
          onForgetAll={forgetAll}
          onAdd={addMemory}
          onClose={() => setShowMemory(false)}
        />
      )}
    </div>
  )
}
