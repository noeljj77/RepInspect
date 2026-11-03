import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'
import Spinner from './Spinner'

/** "Loading …" with a spinner, for data that normally arrives in a moment. */
export default function LoadingLine({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p role="status" className={cn('flex items-center gap-2.5 text-sm text-muted', className)}>
      <Spinner size={15} />
      {children}
    </p>
  )
}
