import { apiFetch, apiPost, apiSend } from './client'

export interface Note {
  id: string
  body: string
  /** The file the note is about, if any (it may have moved since the note was written). */
  path: string | null
  line: number | null
  created_at: string
  updated_at: string
}

export interface NewNote {
  body: string
  path?: string | null
  line?: number | null
}

export interface Collection {
  id: string
  name: string
  description: string | null
  created_at: string
  repository_ids: string[]
}

const notesUrl = (repositoryId: string) => `/api/repositories/${repositoryId}/notes`

export const listNotes = (repositoryId: string) => apiFetch<Note[]>(notesUrl(repositoryId))
export const addNote = (repositoryId: string, note: NewNote) => apiPost<Note>(notesUrl(repositoryId), note)
export const editNote = (repositoryId: string, noteId: string, body: string) =>
  apiSend<Note>('PATCH', `${notesUrl(repositoryId)}/${noteId}`, { body })
export const deleteNote = (repositoryId: string, noteId: string) =>
  apiSend<void>('DELETE', `${notesUrl(repositoryId)}/${noteId}`)

export const listCollections = () => apiFetch<Collection[]>('/api/collections')
export const createCollection = (name: string) => apiPost<Collection>('/api/collections', { name })
export const renameCollection = (id: string, name: string) =>
  apiSend<Collection>('PATCH', `/api/collections/${id}`, { name })
export const deleteCollection = (id: string) => apiSend<void>('DELETE', `/api/collections/${id}`)
export const addToCollection = (id: string, repositoryId: string) =>
  apiSend<void>('PUT', `/api/collections/${id}/repositories/${repositoryId}`)
export const removeFromCollection = (id: string, repositoryId: string) =>
  apiSend<void>('DELETE', `/api/collections/${id}/repositories/${repositoryId}`)
