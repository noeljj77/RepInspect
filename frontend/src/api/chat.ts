import type { Citation } from './ai'
import { apiFetch, apiPost } from './client'

export type IndexStatus = 'missing' | 'pending' | 'building' | 'ready' | 'failed'

/** The search index chat needs. Built after each import; older imports start "missing". */
export interface SearchIndex {
  status: IndexStatus
  chunk_count: number
  chunks_embedded: number
  truncated: boolean
  model: string | null
  error_code: string | null
  error_message: string | null
  completed_at: string | null
}

/** A part of the code the search found and gave to the model. */
export interface Source {
  path: string
  start_line: number
  end_line: number
  symbol: string | null
  /** Which searches found it: "meaning", "keywords", "name". */
  matched_by: string[]
}

export interface AnswerDetails {
  /** False when the code that was searched does not contain the answer. */
  answerable: boolean
  /** [1] in the answer text refers to citations[0], and so on. */
  citations: Citation[]
  removed_citations: number
  ungrounded_paths: string[]
  sources: Source[]
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  status: 'pending' | 'completed' | 'failed'
  content: string
  details: AnswerDetails | null
  error_code: string | null
  error_message: string | null
  model: string | null
  created_at: string
  completed_at: string | null
}

export interface ChatSummary {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface Chat extends ChatSummary {
  messages: ChatMessage[]
}

const base = (repositoryId: string) => `/api/repositories/${repositoryId}`

export const getIndex = (repositoryId: string) => apiFetch<SearchIndex>(`${base(repositoryId)}/index`)
export const buildIndex = (repositoryId: string) => apiPost<SearchIndex>(`${base(repositoryId)}/index`)

export const listChats = (repositoryId: string) => apiFetch<ChatSummary[]>(`${base(repositoryId)}/chats`)
export const getChat = (repositoryId: string, chatId: string) =>
  apiFetch<Chat>(`${base(repositoryId)}/chats/${chatId}`)
export const startChat = (repositoryId: string, question: string) =>
  apiPost<Chat>(`${base(repositoryId)}/chats`, { question })
export const ask = (repositoryId: string, chatId: string, question: string) =>
  apiPost<Chat>(`${base(repositoryId)}/chats/${chatId}/messages`, { question })
export const retryAnswer = (repositoryId: string, chatId: string, messageId: string) =>
  apiPost<Chat>(`${base(repositoryId)}/chats/${chatId}/messages/${messageId}/retry`)
export const deleteChat = (repositoryId: string, chatId: string) =>
  apiFetch<void>(`${base(repositoryId)}/chats/${chatId}`, { method: 'DELETE' })
