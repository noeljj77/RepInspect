import Skeleton from './Skeleton'

/** Shown while a page's code is downloading: grey blocks shaped like a page, with a light sweeping across. */
export default function RouteFallback() {
  return (
    <div role="status">
      <span className="sr-only">Loading…</span>
      <Skeleton className="h-8 w-48" />
      <Skeleton className="mt-6 h-48 rounded-xl" />
    </div>
  )
}
