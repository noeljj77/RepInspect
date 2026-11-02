import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as api from '../api/ai'
import { repositoriesKey } from './useRepositories'

/** How often to re-check while the server is writing an explanation. */
const POLL_MS = 2000

// Under the repository's key, so a new analysis clears these along with its other results.
const explanationKey = (repositoryId: string, kind: api.AiKind, path?: string) =>
  [...repositoriesKey, repositoryId, 'ai', kind, path ?? ''] as const

export function useAiExplanation<K extends api.AiKind>(repositoryId: string, kind: K, path?: string) {
  return useQuery({
    queryKey: explanationKey(repositoryId, kind, path),
    queryFn: () => api.getExplanation(repositoryId, kind, path),
    // A finished explanation only changes when someone regenerates it, and that goes
    // through the mutation below, which updates the cache itself.
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchInterval: (query) => (query.state.data?.status === 'pending' ? POLL_MS : false),
  })
}

export function useRequestExplanation<K extends api.AiKind>(repositoryId: string, kind: K, path?: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.requestExplanation(repositoryId, kind, path),
    // The reply is "pending"; storing it starts the polling above.
    onSuccess: (explanation) => queryClient.setQueryData(explanationKey(repositoryId, kind, path), explanation),
  })
}
