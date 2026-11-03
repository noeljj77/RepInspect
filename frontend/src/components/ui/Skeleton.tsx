import { cn } from '../../lib/cn'

/** A grey placeholder with a light sweeping across it, shaped like the content that is coming. */
export default function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn('skeleton rounded-md', className)} />
}
