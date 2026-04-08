export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  createdAt: number
}

export interface OllamaModel {
  name: string
  size: number
  modified_at: string
}

export type Page = 'chat' | 'image' | 'video' | 'companion' | 'settings'
