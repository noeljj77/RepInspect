import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

import * as api from '../api/repositories'

export const repositoriesKey = ['repositories'] as const

/**
 * Forget the files, file contents and dependencies cached for a repository. A new
 * analysis replaces them. The repository's own query is left alone, because the page
 * is still subscribed to it.
 */
function clearResults(queryClient: QueryClient, id: string) {
  queryClient.removeQueries({
    predicate: (query) =>
      query.queryKey[0] === repositoriesKey[0] && query.queryKey[1] === id && query.queryKey.length > 2,
  })
}

/** How often to re-check while an analysis is still running. */
const POLL_MS = 1500

export function useRepositories() {
  return useQuery({
    queryKey: repositoriesKey,
    queryFn: api.listRepositories,
    refetchInterval: (query) =>
      query.state.data?.some((repo) => api.isInProgress(repo.latest_analysis)) ? POLL_MS : false,
  })
}

export function useRepository(id: string) {
  return useQuery({
    queryKey: [...repositoriesKey, id],
    queryFn: () => api.getRepository(id),
    refetchInterval: (query) => (api.isInProgress(query.state.data?.latest_analysis) ? POLL_MS : false),
  })
}

export function useAddRepository() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.addRepository,
    onSuccess: (repository) => {
      clearResults(queryClient, repository.id) // a retry gets a new analysis; old results are stale
      queryClient.setQueryData([...repositoriesKey, repository.id], repository)
      void queryClient.invalidateQueries({ queryKey: repositoriesKey, exact: true })
    },
  })
}

export function useStartAnalysis(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.startAnalysis(id),
    onSuccess: (repository) => {
      clearResults(queryClient, id)
      queryClient.setQueryData([...repositoriesKey, id], repository)
      void queryClient.invalidateQueries({ queryKey: repositoriesKey, exact: true })
    },
  })
}

// Results of a finished analysis never change (a re-analysis creates a new version),
// so they are fetched once and kept.
const FOREVER = { staleTime: Infinity, refetchOnWindowFocus: false }

export function useFiles(id: string) {
  return useQuery({ queryKey: [...repositoriesKey, id, 'files'], queryFn: () => api.listFiles(id), ...FOREVER })
}

export function useFileContent(id: string, path: string | null) {
  return useQuery({
    queryKey: [...repositoriesKey, id, 'file', path],
    queryFn: () => api.readFile(id, path as string),
    enabled: path !== null,
    ...FOREVER,
  })
}

export function useDependencies(id: string) {
  return useQuery({
    queryKey: [...repositoriesKey, id, 'dependencies'],
    queryFn: () => api.listDependencies(id),
    ...FOREVER,
  })
}
