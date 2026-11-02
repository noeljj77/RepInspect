import { LayoutDashboard, LogOut, type LucideIcon } from 'lucide-react'
import { NavLink, Outlet, useNavigate } from 'react-router'

import { useCurrentUser, useLogout } from '../../hooks/useAuth'
import { cn } from '../../lib/cn'
import { Logo } from '../ui/Logo'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

// Items are added here as each section of the app is built.
const navItems: NavItem[] = [{ to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard }]

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
    <div className="flex items-center justify-between gap-2 border-t border-line px-4 py-3 max-md:hidden md:mt-auto">
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

export default function AppLayout() {
  const signOut = useSignOut()

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[15rem_1fr]">
      <aside className="flex flex-col border-b border-line bg-surface md:min-h-dvh md:border-r md:border-b-0">
        <div className="flex h-16 items-center justify-between px-4 md:px-5">
          <Logo to="/dashboard" />
          {/* On small screens the account menu is hidden, so logging out lives up here. */}
          <button
            type="button"
            onClick={signOut}
            className="text-sm text-muted hover:text-ink md:hidden"
          >
            Log out
          </button>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-3 pb-3 md:flex-col md:pb-0">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex h-9 shrink-0 items-center gap-2.5 rounded-md px-3 text-sm transition-colors',
                  isActive ? 'bg-raised text-ink' : 'text-muted hover:text-ink',
                )
              }
            >
              <Icon size={17} strokeWidth={1.75} aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>
        <AccountMenu />
      </aside>

      <main className="min-w-0 px-4 py-8 sm:px-8 lg:px-12">
        <Outlet />
      </main>
    </div>
  )
}
