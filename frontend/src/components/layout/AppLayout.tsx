import { LayoutDashboard, LogOut } from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router'

import { isInProgress } from '../../api/repositories'
import { useCurrentUser, useLogout } from '../../hooks/useAuth'
import { useRepositories } from '../../hooks/useRepositories'
import { cn } from '../../lib/cn'
import SidebarCollections from '../library/SidebarCollections'
import { Logo } from '../ui/Logo'
import ServiceStatus from './ServiceStatus'

/** Log out, then land on the home page rather than bouncing through the login redirect. */
function useSignOut() {
  const logout = useLogout()
  const navigate = useNavigate()
  return () => logout.mutate(undefined, { onSettled: () => navigate('/', { replace: true }) })
}

function AccountMenu() {
  const { data: user } = useCurrentUser()
  const signOut = useSignOut()

  return (
    <div className="flex items-center justify-between gap-2 border-t border-line px-4 py-3">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{user?.display_name}</p>
        <p className="truncate text-xs text-muted">{user?.email}</p>
      </div>
      <button
        type="button"
        onClick={signOut}
        aria-label="Log out"
        title="Log out"
        className="rounded-md p-2 text-muted transition-colors hover:bg-raised hover:text-ink"
      >
        <LogOut size={17} strokeWidth={1.75} aria-hidden="true" />
      </button>
    </div>
  )
}

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'flex h-8 min-w-0 items-center gap-2.5 rounded-md px-2.5 text-sm transition-colors',
    isActive ? 'bg-raised text-ink' : 'text-muted hover:bg-raised/50 hover:text-ink',
  )

/** Every repository in the library, one click away from any page. */
function SidebarRepositories() {
  const { data: repositories = [] } = useRepositories()

  return (
    <section aria-labelledby="sidebar-repositories">
      <h2 id="sidebar-repositories" className="mb-1.5 px-2.5 text-xs text-faint">
        Repositories
      </h2>
      {repositories.length === 0 ? (
        <p className="px-2.5 text-sm text-faint">None yet</p>
      ) : (
        <ul className="space-y-px">
          {repositories.map((repository) => {
            const analysis = repository.latest_analysis
            const dot = isInProgress(analysis)
              ? 'animate-pulse bg-mark'
              : analysis?.status === 'failed'
                ? 'bg-danger'
                : 'bg-line'
            return (
              <li key={repository.id}>
                <NavLink
                  to={`/repositories/${repository.id}`}
                  className={linkClass}
                  title={`${repository.owner ? `${repository.owner}/` : ''}${repository.name}`}
                >
                  <span aria-hidden="true" className={cn('size-1.5 shrink-0 rounded-full', dot)} />
                  <span className="truncate">{repository.name}</span>
                </NavLink>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

export default function AppLayout() {
  const signOut = useSignOut()

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[15.5rem_1fr]">
      <aside className="flex flex-col border-b border-line bg-surface md:sticky md:top-0 md:h-dvh md:border-r md:border-b-0">
        <div className="flex h-14 shrink-0 items-center justify-between px-4">
          <Logo to="/dashboard" />
          {/* On small screens the account menu is hidden, so logging out lives up here. */}
          <button type="button" onClick={signOut} className="text-sm text-muted hover:text-ink md:hidden">
            Log out
          </button>
        </div>
        <nav aria-label="Main" className="px-2 pb-3 md:pb-0">
          <NavLink to="/dashboard" className={linkClass}>
            <LayoutDashboard size={16} strokeWidth={1.75} aria-hidden="true" />
            Dashboard
          </NavLink>
        </nav>
        <div className="hidden min-h-0 flex-1 space-y-6 overflow-y-auto px-2 py-5 md:block">
          <SidebarRepositories />
          <SidebarCollections />
        </div>
        <div className="hidden md:block">
          <ServiceStatus />
          <AccountMenu />
        </div>
      </aside>

      <main className="min-w-0 px-4 py-8 sm:px-8 lg:px-12">
        <Outlet />
      </main>
    </div>
  )
}
