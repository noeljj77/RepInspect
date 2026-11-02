import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as api from '../api/repositories'

export const repositoriesKey = ['repositories'] as const

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
      queryClient.setQueryData([...repositoriesKey, id], repository)
      void queryClient.invalidateQueries({ queryKey: repositoriesKey, exact: true })
    },
  })
}
