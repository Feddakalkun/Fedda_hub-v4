import { useEffect, useRef, useState } from 'react'
import { listModels } from '../services/ollama'

export function useOllamaModels() {
  const [models, setModels] = useState<string[]>([])
  const [online, setOnline] = useState(false)
  const [loading, setLoading] = useState(true)

  const refresh = () => {
    setLoading(true)
    listModels()
      .then(m => { setModels(m); setOnline(true) })
      .catch(() => { setModels([]); setOnline(false) })
      .finally(() => setLoading(false))
  }

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    refresh()
    intervalRef.current = setInterval(refresh, 15_000)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [])

  return { models, online, loading, refresh }
}
