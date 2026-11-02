import { LayoutDashboard, type LucideIcon } from 'lucide-react'
import { NavLink, Outlet } from 'react-router'

import { cn } from '../../lib/cn'
import { Logo } from '../ui/Logo'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

// Items are added here as each section of the app is built.
const navItems: NavItem[] = [{ to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard }]

export default function AppLayout() {
  return (
    <div className="min-h-dvh md:grid md:grid-cols-[15rem_1fr]">
      <aside className="border-b border-line bg-surface md:min-h-dvh md:border-r md:border-b-0">
        <div className="flex h-16 items-center px-4 md:px-5">
          <Logo to="/dashboard" />
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
      </aside>

      <main className="min-w-0 px-4 py-8 sm:px-8 lg:px-12">
        <Outlet />
      </main>
    </div>
  )
}
