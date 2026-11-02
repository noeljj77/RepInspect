import type { ReactNode } from 'react'

import { Logo } from '../ui/Logo'

interface AuthShellProps {
  title: string
  description: string
  children: ReactNode
  footer: ReactNode
}

/** Centered card used by the login and register pages. */
export default function AuthShell({ title, description, children, footer }: AuthShellProps) {
  return (
    <div className="flex min-h-dvh flex-col items-center px-4 pt-10 pb-12 sm:pt-20">
      <Logo />
      <main className="mt-10 w-full max-w-sm">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-2 text-muted">{description}</p>
        <div className="mt-8">{children}</div>
        <p className="mt-8 text-sm text-muted">{footer}</p>
      </main>
    </div>
  )
}
