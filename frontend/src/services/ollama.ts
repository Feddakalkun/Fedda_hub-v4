// Ollama API service — streams completions token by token

const BASE = '/ollama'

export async function listModels(): Promise<string[]> {
  const res = await fetch(`${BASE}/api/tags`)
  if (!res.ok) throw new Error('Ollama unreachable')
  const data = await res.json()
  return (data.models ?? []).map((m: { name: string }) => m.name)
}

export async function* streamChat(
  model: string,
  messages: { role: string; content: string }[],
  signal?: AbortSignal,
): AsyncGenerator<string> {
  const res = await fetch(`${BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, messages, stream: true }),
    signal,
  })

  if (!res.ok) throw new Error(`Ollama error ${res.status}`)
  if (!res.body) throw new Error('No response body')

  const reader = res.body.getReader()
  const dec = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const chunk = dec.decode(value, { stream: true })
    for (const line of chunk.split('\n')) {
      if (!line.trim()) continue
      try {
        const json = JSON.parse(line)
        const token: string = json?.message?.content ?? ''
        if (token) yield token
        if (json.done) return
      } catch { /* partial chunk */ }
    }
  }
}
