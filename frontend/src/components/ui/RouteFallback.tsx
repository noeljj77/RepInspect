/** Shown while a page's code is downloading, in the same grey as the other loading placeholders. */
export default function RouteFallback() {
  return (
    <div role="status" className="animate-pulse">
      <span className="sr-only">Loading…</span>
      <div className="h-8 w-48 rounded-md bg-raised" />
      <div className="mt-6 h-48 rounded-xl border border-line bg-surface" />
    </div>
  )
}
