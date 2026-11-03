import { useQuery } from '@tanstack/react-query'

import { getHealth } from '../../api/health'
import { cn } from '../../lib/cn'

function Row({ label, ok, value }: { label: string; ok: boolean | null; value: string }) {
  return (
    <div className="flex items-center justify-between py-1">
      <dt className="text-faint">{label}</dt>
      <dd className="flex items-center gap-1.5">
        <span
          aria-hidden="true"
          className={cn('size-1.5 rounded-full', ok === null ? 'bg-faint' : ok ? 'bg-ok' : 'bg-danger')}
        />
        {value}
      </dd>
    </div>
  )
}

/** A quiet line at the foot of the sidebar; the details open on demand. */
export default function ServiceStatus() {
  const { data, isPending, isError } = useQuery({ queryKey: ['health'], queryFn: getHealth })

  const apiOk = isPending ? null : !isError
  const dbOk = data ? data.database === 'ok' : isPending ? null : false
  const allOk = apiOk === true && dbOk === true
  const summary = isPending ? 'Checking services' : allOk ? 'All services running' : 'A service is not responding'

  return (
    <details className="group border-t border-line px-4 py-2.5 text-xs">
      <summary className="flex cursor-pointer list-none items-center gap-2 text-muted hover:text-ink">
        <span
          aria-hidden="true"
          className={cn('size-1.5 rounded-full', isPending ? 'bg-faint' : allOk ? 'bg-ok' : 'bg-danger')}
        />
        {summary}
      </summary>
      <dl className="mt-1.5" aria-label="Service status">
        <Row label="API" ok={apiOk} value={isPending ? 'Checking' : isError ? 'Unreachable' : 'Running'} />
        <Row label="Database" ok={dbOk} value={isPending ? 'Checking' : dbOk ? 'Connected' : 'Unavailable'} />
        {data && <Row label="Version" ok={null} value={data.version} />}
      </dl>
    </details>
  )
}
