import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as api from '../api/library'
import { repositoriesKey } from './useRepositories'

const notesKey = (repositoryId: string) => [...repositoriesKey, repositoryId, 'notes'] as const
const collectionsKey = ['collections'] as const

export function useNotes(repositoryId: string) {
  return useQuery({ queryKey: notesKey(repositoryId), queryFn: () => api.listNotes(repositoryId) })
}

function useRefreshNotes(repositoryId: string) {
  const queryClient = useQueryClient()
  return () => void queryClient.invalidateQueries({ queryKey: notesKey(repositoryId) })
}

export function useAddNote(repositoryId: string) {
  const refresh = useRefreshNotes(repositoryId)
  return useMutation({ mutationFn: (note: api.NewNote) => api.addNote(repositoryId, note), onSuccess: refresh })
}

export function useEditNote(repositoryId: string) {
  const refresh = useRefreshNotes(repositoryId)
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: string }) => api.editNote(repositoryId, id, body),
    onSuccess: refresh,
  })
}

export function useDeleteNote(repositoryId: string) {
  const refresh = useRefreshNotes(repositoryId)
  return useMutation({ mutationFn: (noteId: string) => api.deleteNote(repositoryId, noteId), onSuccess: refresh })
}

export function useCollections() {
  return useQuery({ queryKey: collectionsKey, queryFn: api.listCollections })
}

/** Collections and repositories both show membership, so both are reloaded. */
function useRefreshLibrary() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: collectionsKey })
    void queryClient.invalidateQueries({ queryKey: repositoriesKey })
  }
}

export function useCreateCollection() {
  const refresh = useRefreshLibrary()
  return useMutation({ mutationFn: api.createCollection, onSuccess: refresh })
}

export function useRenameCollection() {
  const refresh = useRefreshLibrary()
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => api.renameCollection(id, name),
    onSuccess: refresh,
  })
}

export function useDeleteCollection() {
  const refresh = useRefreshLibrary()
  return useMutation({ mutationFn: api.deleteCollection, onSuccess: refresh })
}

export function useToggleCollection(repositoryId: string) {
  const refresh = useRefreshLibrary()
  return useMutation({
    mutationFn: ({ id, member }: { id: string; member: boolean }) =>
      member ? api.addToCollection(id, repositoryId) : api.removeFromCollection(id, repositoryId),
    onSuccess: refresh,
  })
}
