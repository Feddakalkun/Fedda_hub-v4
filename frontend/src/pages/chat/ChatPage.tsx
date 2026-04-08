import { useCallback, useEffect, useRef, useState } from 'react'
import { Send, StopCircle, RefreshCw, ChevronDown, Bot } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { streamChat } from '../../services/ollama'
import { useOllamaModels } from '../../hooks/useOllamaModels'
import type { Message } from '../../types'

function uid() { return Math.random().toString(36).slice(2) }

export function ChatPage() {
  const { models, online, loading, refresh } = useOllamaModels()
  const [model, setModel] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Pick first model automatically
  useEffect(() => { if (!model && models.length) setModel(models[0]) }, [models, model])

  // Auto-scroll
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const send = useCallback(async () => {
    const text = input.trim()
    if (!text || !model || streaming) return

    const userMsg: Message = { id: uid(), role: 'user', content: text, createdAt: Date.now() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setStreaming(true)

    const assistantId = uid()
    setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '', createdAt: Date.now() }])

    const ctrl = new AbortController()
    abortRef.current = ctrl

    try {
      const history = [...messages, userMsg].map(m => ({ role: m.role, content: m.content }))
      for await (const token of streamChat(model, history, ctrl.signal)) {
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: m.content + token } : m
        ))
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name !== 'AbortError') {
        setMessages(prev => prev.map(m =>
          m.id === assistantId ? { ...m, content: '⚠️ Error: ' + e.message } : m
        ))
      }
    } finally {
      setStreaming(false)
      abortRef.current = null
    }
  }, [input, model, messages, streaming])

  const stop = () => abortRef.current?.abort()

  const clear = () => { if (!streaming) setMessages([]) }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
  }

  return (
    <div className="flex flex-col h-full">

      {/* ── Header ── */}
      <div className="flex items-center justify-between px-5 h-12 shrink-0"
        style={{ borderBottom: '1px solid var(--border)' }}>
        <div className="flex items-center gap-2">
          <Bot size={16} className="text-violet-400" />
          <span className="text-sm font-semibold text-white/80">LLM Chat</span>

          {/* Online dot */}
          <span className="w-1.5 h-1.5 rounded-full"
            style={{ background: loading ? '#64748b' : online ? '#4ade80' : '#f87171' }} />
        </div>

        <div className="flex items-center gap-2">
          {/* Model picker */}
          {models.length > 0 && (
            <div className="relative">
              <select value={model} onChange={e => setModel(e.target.value)}
                className="appearance-none pl-3 pr-7 py-1 rounded-lg text-xs font-medium text-white/70 outline-none cursor-pointer"
                style={{ background: 'var(--bg-input)', border: '1px solid var(--border)' }}>
                {models.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
              <ChevronDown size={12} className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-white/30" />
            </div>
          )}

          {!online && !loading && (
            <span className="text-[10px] text-red-400/70 uppercase tracking-widest">Ollama offline</span>
          )}

          <button onClick={refresh} title="Refresh models"
            className="p-1.5 rounded-lg text-white/30 hover:text-white/70 transition-colors"
            style={{ background: 'var(--bg-input)' }}>
            <RefreshCw size={12} />
          </button>

          <button onClick={clear} disabled={streaming || messages.length === 0}
            className="px-2.5 py-1 rounded-lg text-[10px] uppercase tracking-widest text-white/30 hover:text-white/60 disabled:opacity-30 transition-colors"
            style={{ background: 'var(--bg-input)' }}>
            Clear
          </button>
        </div>
      </div>

      {/* ── Messages ── */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-3 opacity-30 select-none">
            <Bot size={36} className="text-violet-400" />
            <p className="text-sm">Start a conversation</p>
            {!online && !loading && (
              <p className="text-xs text-red-400">Ollama is not running — start it with <code>ollama serve</code></p>
            )}
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
            {/* Avatar */}
            <div className="w-7 h-7 rounded-full shrink-0 flex items-center justify-center text-[10px] font-bold"
              style={msg.role === 'user'
                ? { background: 'linear-gradient(135deg, #8b5cf6, #6366f1)', color: '#fff' }
                : { background: '#1a1a2e', color: '#a78bfa', border: '1px solid rgba(167,139,250,0.2)' }
              }>
              {msg.role === 'user' ? 'U' : 'AI'}
            </div>

            {/* Bubble */}
            <div className="max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed"
              style={msg.role === 'user'
                ? { background: 'linear-gradient(135deg, rgba(139,92,246,0.15), rgba(99,102,241,0.15))', border: '1px solid rgba(139,92,246,0.2)', color: '#e2e2f0' }
                : { background: 'var(--bg-surface)', border: '1px solid var(--border)', color: '#c4c4d8' }
              }>
              {msg.role === 'assistant'
                ? <ReactMarkdown>{msg.content || (streaming ? '▌' : '')}</ReactMarkdown>
                : msg.content}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* ── Input ── */}
      <div className="px-4 pb-4 shrink-0">
        <div className="flex items-end gap-2 rounded-2xl p-3"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
          <textarea
            rows={1}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={online ? `Message ${model || '…'}` : 'Ollama offline'}
            disabled={!online || streaming}
            className="flex-1 resize-none bg-transparent text-sm text-white/80 placeholder:text-white/20 outline-none max-h-40 disabled:opacity-40"
            style={{ lineHeight: '1.5' }}
          />
          <button
            onClick={streaming ? stop : send}
            disabled={!online || (!streaming && !input.trim())}
            className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0 transition-all duration-200 disabled:opacity-20"
            style={streaming
              ? { background: 'rgba(248,113,113,0.15)', border: '1px solid rgba(248,113,113,0.3)', color: '#f87171' }
              : { background: 'linear-gradient(135deg, #8b5cf6, #6366f1)', color: '#fff' }
            }>
            {streaming ? <StopCircle size={15} /> : <Send size={15} />}
          </button>
        </div>
        <p className="text-center text-[9px] text-white/10 mt-1.5 tracking-widest uppercase">
          Enter to send · Shift+Enter for newline
        </p>
      </div>
    </div>
  )
}
