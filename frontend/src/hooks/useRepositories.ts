import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

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

/** Store a repository returned by a mutation and refresh the library list. */
function useSaveRepository() {
  const queryClient = useQueryClient()
  return (repository: api.RepositoryDetail) => {
    queryClient.setQueryData([...repositoriesKey, repository.id], repository)
    void queryClient.invalidateQueries({ queryKey: repositoriesKey, exact: true })
  }
}

/**
 * Start a new analysis: a retry, or a refresh. The current version's results stay valid
 * (and on screen) until the new version finishes; see useReloadOnNewVersion.
 */
export function useStartAnalysis(id: string) {
  const save = useSaveRepository()
  return useMutation({ mutationFn: () => api.startAnalysis(id), onSuccess: save })
}

/** When the version on screen changes (a refresh finished), fetch its files and results. */
export function useReloadOnNewVersion(repository: api.RepositoryDetail | undefined) {
  const queryClient = useQueryClient()
  const shown = useRef<string | null | undefined>(undefined)
  const currentId = repository?.current_analysis?.id ?? null
  useEffect(() => {
    if (shown.current !== undefined && shown.current !== currentId && repository) {
      void queryClient.invalidateQueries({
        predicate: (query) =>
          query.queryKey[0] === repositoriesKey[0] &&
          query.queryKey[1] === repository.id &&
          query.queryKey.length > 2,
      })
    }
    shown.current = currentId
  }, [currentId, queryClient, repository])
}

export function useUpdateLabels(id: string) {
  const save = useSaveRepository()
  return useMutation({ mutationFn: (labels: string[]) => api.updateLabels(id, labels), onSuccess: save })
}

export function useDeleteRepository(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.deleteRepository(id),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: [...repositoriesKey, id] })
      void queryClient.invalidateQueries({ queryKey: repositoriesKey, exact: true })
      void queryClient.invalidateQueries({ queryKey: ['collections'] })
    },
  })
}

export function useUploadZip() {
  const save = useSaveRepository()
  return useMutation({ mutationFn: api.uploadZip, onSuccess: save })
}

export function useUploadNewVersion(id: string) {
  const save = useSaveRepository()
  return useMutation({ mutationFn: (file: File) => api.uploadNewVersion(id, file), onSuccess: save })
}

export function useVersions(id: string, latestStatus: string | undefined) {
  return useQuery({
    // The newest status is part of the key, so the list reloads when a refresh moves on.
    queryKey: [...repositoriesKey, id, 'versions', latestStatus],
    queryFn: () => api.listVersions(id),
  })
}

export function useVersionChanges(id: string, analysisId: string, enabled: boolean) {
  return useQuery({
    queryKey: [...repositoriesKey, id, 'changes', analysisId],
    queryFn: () => api.versionChanges(id, analysisId),
    enabled,
    ...FOREVER,
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
