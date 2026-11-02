import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import * as authApi from '../api/auth'

export const currentUserKey = ['auth', 'me'] as const

/** The logged-in user: undefined while loading, null when logged out. */
export function useCurrentUser() {
  return useQuery({
    queryKey: currentUserKey,
    queryFn: authApi.getCurrentUser,
    staleTime: 5 * 60 * 1000,
  })
}

/** Login and register both end the same way: the server sets the cookie and returns the user. */
function useStoreSignedInUser() {
  const queryClient = useQueryClient()
  return (user: authApi.User) => {
    // Drop anything cached for a previous account before showing the new one.
    queryClient.clear()
    queryClient.setQueryData(currentUserKey, user)
  }
}

export function useLogin() {
  const storeUser = useStoreSignedInUser()
  return useMutation({ mutationFn: authApi.login, onSuccess: storeUser })
}

export function useRegister() {
  const storeUser = useStoreSignedInUser()
  return useMutation({ mutationFn: authApi.register, onSuccess: storeUser })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: authApi.logout,
    onSettled: () => {
      // Clear everything so the next person on this browser sees none of it.
      queryClient.clear()
      queryClient.setQueryData(currentUserKey, null)
    },
  })
}
