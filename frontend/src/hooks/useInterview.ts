import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as api from '../api/interview'
import { repositoriesKey } from './useRepositories'

const POLL_MS = 2000
const questionsKey = (repositoryId: string) => [...repositoriesKey, repositoryId, 'questions'] as const

export function useQuestions(repositoryId: string) {
  return useQuery({
    queryKey: questionsKey(repositoryId),
    queryFn: () => api.getQuestions(repositoryId),
    refetchInterval: (query) => (query.state.data?.latest_batch?.status === 'pending' ? POLL_MS : false),
  })
}

export function useGenerateQuestions(repositoryId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: api.GenerateRequest) => api.generateQuestions(repositoryId, request),
    // The reply says "pending"; storing it starts the polling above.
    onSuccess: (data) => queryClient.setQueryData(questionsKey(repositoryId), data),
  })
}

export function useUpdateQuestion(repositoryId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...change }: { id: string; status?: api.Progress; user_answer?: string | null }) =>
      api.updateQuestion(repositoryId, id, change),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: questionsKey(repositoryId) }),
  })
}

export function useDeleteQuestion(repositoryId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.deleteQuestion(repositoryId, id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: questionsKey(repositoryId) }),
  })
}
