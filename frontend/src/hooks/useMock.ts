import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as api from '../api/mock'
import { repositoriesKey } from './useRepositories'

const POLL_MS = 1500
const listKey = (repositoryId: string) => [...repositoriesKey, repositoryId, 'mock-interviews'] as const
const interviewKey = (repositoryId: string, id: string) => [...listKey(repositoryId), id] as const

/** True while the server is still working on something the page waits for. */
const busy = (interview: api.MockInterview | undefined) =>
  interview?.status === 'preparing' || Boolean(interview?.turns.some((turn) => turn.status === 'grading'))

export function useInterviews(repositoryId: string) {
  return useQuery({ queryKey: listKey(repositoryId), queryFn: () => api.listInterviews(repositoryId) })
}

export function useInterview(repositoryId: string, id: string) {
  return useQuery({
    queryKey: interviewKey(repositoryId, id),
    queryFn: () => api.getInterview(repositoryId, id),
    refetchInterval: (query) => (busy(query.state.data) ? POLL_MS : false),
  })
}

function useSave(repositoryId: string) {
  const queryClient = useQueryClient()
  return (interview: api.MockInterview) => {
    queryClient.setQueryData(interviewKey(repositoryId, interview.id), interview)
    void queryClient.invalidateQueries({ queryKey: listKey(repositoryId), exact: true })
    // Writing missing questions adds to the practice list.
    void queryClient.invalidateQueries({ queryKey: [...repositoriesKey, repositoryId, 'questions'] })
  }
}

export function useStartInterview(repositoryId: string) {
  const save = useSave(repositoryId)
  return useMutation({ mutationFn: (request: api.StartRequest) => api.startInterview(repositoryId, request), onSuccess: save })
}

export function useInterviewActions(repositoryId: string, id: string) {
  const save = useSave(repositoryId)
  const queryClient = useQueryClient()
  return {
    answer: useMutation({ mutationFn: (text: string) => api.answerQuestion(repositoryId, id, text), onSuccess: save }),
    skip: useMutation({ mutationFn: () => api.skipQuestion(repositoryId, id), onSuccess: save }),
    retry: useMutation({ mutationFn: (turnId: string) => api.retryGrading(repositoryId, id, turnId), onSuccess: save }),
    finish: useMutation({ mutationFn: () => api.finishInterview(repositoryId, id), onSuccess: save }),
    remove: useMutation({
      mutationFn: () => api.deleteInterview(repositoryId, id),
      onSuccess: () => {
        queryClient.removeQueries({ queryKey: interviewKey(repositoryId, id) })
        void queryClient.invalidateQueries({ queryKey: listKey(repositoryId), exact: true })
      },
    }),
  }
}
