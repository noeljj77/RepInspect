import { Navigate, Outlet, useLocation } from 'react-router'

import { useCurrentUser } from '../../hooks/useAuth'

function CheckingSession() {
  return (
    <div role="status" className="grid min-h-dvh place-items-center text-sm text-muted">
      Checking your session…
    </div>
  )
}

/** Wraps routes that need a logged-in user; guests are sent to the login page. */
export function RequireAuth() {
  const { data: user, isPending } = useCurrentUser()
  const location = useLocation()

  if (isPending) return <CheckingSession />
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  return <Outlet />
}

/** Wraps login and register; people who are already logged in go to the dashboard. */
export function GuestOnly() {
  const { data: user, isPending } = useCurrentUser()

  if (isPending) return <CheckingSession />
  if (user) return <Navigate to="/dashboard" replace />
  return <Outlet />
}
