import { useCallback, useEffect, useRef, useState } from "react"
import { Send, StopCircle, RefreshCw, ChevronDown, Bot, Terminal, ChevronRight } from "lucide-react"
import ReactMarkdown from "react-markdown"
import { useOllamaModels } from "../../hooks/useOllamaModels"
import type { Message } from "../../types"

function uid() { return Math.random().toString(36).slice(2) }

interface ToolCall {
  name: string
  args: Record<string, unknown>
  result?: string
  open: boolean
}

interface AgentMessage extends Message {
  toolCalls?: ToolCall[]
}

// ── Tool call card ───────────────────────────────────────────────────────────
function ToolCard({ tc, onToggle }: { tc: ToolCall; onToggle: () => void }) {
  const pending = tc.result === undefined
  return (
    <div className="mt-2 rounded-xl overflow-hidden text-xs"
      style={{ background: "#0d0d1a", border: "1px solid rgba(139,92,246,0.2)" }}>
      <button onClick={onToggle}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-white/[0.03] transition-colors">
        <Terminal size={12} className="text-violet-400 shrink-0" />
        <span className="font-mono text-violet-300 font-medium">{tc.name}</span>
        {Object.entries(tc.args).map(([k, v]) => (
          <span key={k} className="text-white/30">{String(v).slice(0, 40)}</span>
        ))}
        <span className="ml-auto flex items-center gap-1.5">
          {pending
            ? <span className="text-yellow-400/60 animate-pulse">running…</span>
            : <span className="text-green-400/60">done</span>}
          <ChevronRight size={11}
            className={`text-white/20 transition-transform ${tc.open ? "rotate-90" : ""}`} />
        </span>
      </button>
      {tc.open && tc.result !== undefined && (
        <pre className="px-3 pb-3 text-[10px] text-white/40 overflow-x-auto whitespace-pre-wrap leading-relaxed">
          {tc.result}
        </pre>
      )}
    </div>
  )
}

// ── Chat message ─────────────────────────────────────────────────────────────
function ChatMessage({
  msg, streaming, onToggleTool,
}: {
  msg: AgentMessage
  streaming: boolean
  onToggleTool: (msgId: string, i: number) => void
}) {
  const isUser = msg.role === "user"
  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      <div className="w-7 h-7 rounded-full shrink-0 flex items-center justify-center text-[10px] font-bold"
        style={isUser
          ? { background: "linear-gradient(135deg, #8b5cf6, #6366f1)", color: "#fff" }
          : { background: "#1a1a2e", color: "#a78bfa", border: "1px solid rgba(167,139,250,0.2)" }
        }>
        {isUser ? "U" : "AI"}
      </div>
      <div className={`max-w-[75%] ${isUser ? "items-end" : "items-start"} flex flex-col gap-1`}>
        {/* Tool calls */}
        {msg.toolCalls?.map((tc, i) => (
          <ToolCard key={i} tc={tc} onToggle={() => onToggleTool(msg.id, i)} />
        ))}
        {/* Text bubble */}
        {(msg.content || (streaming && msg.role === "assistant")) && (
          <div className="rounded-2xl px-4 py-2.5 text-sm leading-relaxed prose prose-invert max-w-none"
            style={isUser
              ? { background: "linear-gradient(135deg, rgba(139,92,246,0.15), rgba(99,102,241,0.15))", border: "1px solid rgba(139,92,246,0.2)", color: "#e2e2f0" }
              : { background: "var(--bg-surface)", border: "1px solid var(--border)", color: "#c4c4d8" }
            }>
            {msg.role === "assistant"
              ? <ReactMarkdown>{msg.content || (streaming ? "▌" : "")}</ReactMarkdown>
              : msg.content}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main chat page ────────────────────────────────────────────────────────────
export function ChatPage() {
  const { models, online, loading, refresh } = useOllamaModels()
  const [model, setModel] = useState("")
  const [messages, setMessages] = useState<AgentMessage[]>([])
  const [input, setInput] = useState("")
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { if (!model && models.length) setModel(models[0]) }, [models, model])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }) }, [messages])

  const toggleTool = (msgId: string, idx: number) => {
    setMessages(prev => prev.map(m =>
      m.id !== msgId ? m : {
        ...m,
        toolCalls: m.toolCalls?.map((tc, i) => i === idx ? { ...tc, open: !tc.open } : tc),
      }
    ))
  }

  const send = useCallback(async () => {
    const text = input.trim()
    if (!text || !model || streaming) return

    const userMsg: AgentMessage = { id: uid(), role: "user", content: text, createdAt: Date.now() }
    const assistantId = uid()
    setMessages(prev => [
      ...prev,
      userMsg,
      { id: assistantId, role: "assistant", content: "", createdAt: Date.now(), toolCalls: [] },
    ])
    setInput("")
    setStreaming(true)

    const ctrl = new AbortController()
    abortRef.current = ctrl

    try {
      const history = [...messages, userMsg].map(m => ({ role: m.role, content: m.content }))
      const res = await fetch("/api/agent/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model, messages: history }),
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
            } else if (ev.type === "tool_start") {
              setMessages(prev => prev.map(m =>
                m.id !== assistantId ? m : {
                  ...m,
                  toolCalls: [...(m.toolCalls ?? []), { name: ev.name, args: ev.args, open: false }],
                }
              ))
            } else if (ev.type === "tool_end") {
              setMessages(prev => prev.map(m =>
                m.id !== assistantId ? m : {
                  ...m,
                  toolCalls: m.toolCalls?.map(tc =>
                    tc.name === ev.name && tc.result === undefined ? { ...tc, result: ev.result } : tc
                  ),
                }
              ))
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
  }, [input, model, messages, streaming])

  const stop = () => abortRef.current?.abort()
  const clear = () => { if (!streaming) setMessages([]) }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-5 h-12 shrink-0"
        style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="flex items-center gap-2">
          <Bot size={16} className="text-violet-400" />
          <span className="text-sm font-semibold text-white/80">Agent</span>
          <span className="text-[9px] px-1.5 py-0.5 rounded-md uppercase tracking-widest font-medium"
            style={{ background: "rgba(139,92,246,0.1)", color: "#a78bfa", border: "1px solid rgba(139,92,246,0.2)" }}>
            tool-use
          </span>
          <span className="w-1.5 h-1.5 rounded-full"
            style={{ background: loading ? "#64748b" : online ? "#4ade80" : "#f87171" }} />
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
          {!online && !loading && (
            <span className="text-[10px] text-red-400/70 uppercase tracking-widest">Ollama offline</span>
          )}
          <button onClick={refresh} title="Refresh"
            className="p-1.5 rounded-lg text-white/30 hover:text-white/70 transition-colors"
            style={{ background: "var(--bg-input)" }}>
            <RefreshCw size={12} />
          </button>
          <button onClick={clear} disabled={streaming || messages.length === 0}
            className="px-2.5 py-1 rounded-lg text-[10px] uppercase tracking-widest text-white/30 hover:text-white/60 disabled:opacity-30 transition-colors"
            style={{ background: "var(--bg-input)" }}>
            Clear
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-4 opacity-30 select-none">
            <Bot size={36} className="text-violet-400" />
            <p className="text-sm">Ask me anything — I can run commands, read files, search the web</p>
            <div className="flex flex-wrap gap-2 justify-center text-[10px]">
              {["What files are in my Downloads?", "How much RAM am I using?", "Search for LTX video model", "Run ipconfig"].map(ex => (
                <button key={ex} onClick={() => setInput(ex)}
                  className="px-2.5 py-1 rounded-lg text-white/40 hover:text-white/70 transition-colors"
                  style={{ border: "1px solid var(--border)", background: "var(--bg-surface)" }}>
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map(msg => (
          <ChatMessage key={msg.id} msg={msg} streaming={streaming} onToggleTool={toggleTool} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 pb-4 shrink-0">
        <div className="flex items-end gap-2 rounded-2xl p-3"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)" }}>
          <textarea rows={1} value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send() } }}
            placeholder={online ? `Ask ${model || "the agent"} anything…` : "Ollama offline"}
            disabled={!online || streaming}
            className="flex-1 resize-none bg-transparent text-sm text-white/80 placeholder:text-white/20 outline-none max-h-40 disabled:opacity-40"
          />
          <button onClick={streaming ? stop : send}
            disabled={!online || (!streaming && !input.trim())}
            className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0 transition-all duration-200 disabled:opacity-20"
            style={streaming
              ? { background: "rgba(248,113,113,0.15)", border: "1px solid rgba(248,113,113,0.3)", color: "#f87171" }
              : { background: "linear-gradient(135deg, #8b5cf6, #6366f1)", color: "#fff" }
            }>
            {streaming ? <StopCircle size={15} /> : <Send size={15} />}
          </button>
        </div>
        <p className="text-center text-[9px] text-white/10 mt-1.5 tracking-widest uppercase">
          Enter · Shift+Enter for newline · Uses tool calling — try qwen2.5 or llama3.1
        </p>
      </div>
    </div>
  )
}
