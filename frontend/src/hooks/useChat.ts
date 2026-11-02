import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as api from '../api/chat'
import { repositoriesKey } from './useRepositories'

/** How often to re-check while the index is being built or an answer is being written. */
const POLL_MS = 1500

// Under the repository's key, so a new analysis clears these with its other results.
const indexKey = (repositoryId: string) => [...repositoriesKey, repositoryId, 'index'] as const
const chatsKey = (repositoryId: string) => [...repositoriesKey, repositoryId, 'chats'] as const
const chatKey = (repositoryId: string, chatId: string) => [...chatsKey(repositoryId), chatId] as const

const building = (index: api.SearchIndex | undefined) => index?.status === 'pending' || index?.status === 'building'

export function useSearchIndex(repositoryId: string) {
  return useQuery({
    queryKey: indexKey(repositoryId),
    queryFn: () => api.getIndex(repositoryId),
    refetchInterval: (query) => (building(query.state.data) ? POLL_MS : false),
  })
}

export function useBuildIndex(repositoryId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.buildIndex(repositoryId),
    onSuccess: (index) => queryClient.setQueryData(indexKey(repositoryId), index),
  })
}

export function useChats(repositoryId: string) {
  return useQuery({ queryKey: chatsKey(repositoryId), queryFn: () => api.listChats(repositoryId) })
}

export function useChat(repositoryId: string, chatId: string | null) {
  return useQuery({
    queryKey: chatKey(repositoryId, chatId ?? ''),
    queryFn: () => api.getChat(repositoryId, chatId as string),
    enabled: chatId !== null,
    refetchInterval: (query) =>
      query.state.data?.messages.some((message) => message.status === 'pending') ? POLL_MS : false,
  })
}

/** Store a conversation returned by the server and refresh the list (its order may change). */
function useSaveChat(repositoryId: string) {
  const queryClient = useQueryClient()
  return (chat: api.Chat) => {
    queryClient.setQueryData(chatKey(repositoryId, chat.id), chat)
    void queryClient.invalidateQueries({ queryKey: chatsKey(repositoryId), exact: true })
  }
}

export function useStartChat(repositoryId: string) {
  const save = useSaveChat(repositoryId)
  return useMutation({
    mutationFn: (question: string) => api.startChat(repositoryId, question),
    onSuccess: save,
  })
}

export function useAsk(repositoryId: string, chatId: string) {
  const save = useSaveChat(repositoryId)
  return useMutation({
    mutationFn: (question: string) => api.ask(repositoryId, chatId, question),
    onSuccess: save,
  })
}

export function useRetryAnswer(repositoryId: string, chatId: string) {
  const save = useSaveChat(repositoryId)
  return useMutation({
    mutationFn: (messageId: string) => api.retryAnswer(repositoryId, chatId, messageId),
    onSuccess: save,
  })
}

export function useDeleteChat(repositoryId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (chatId: string) => api.deleteChat(repositoryId, chatId),
    onSuccess: (_, chatId) => {
      queryClient.removeQueries({ queryKey: chatKey(repositoryId, chatId) })
      void queryClient.invalidateQueries({ queryKey: chatsKey(repositoryId), exact: true })
    },
  })
}
