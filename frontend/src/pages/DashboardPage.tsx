import { useQuery } from '@tanstack/react-query'
import { FolderGit2 } from 'lucide-react'

import { getHealth } from '../api/health'
import { cn } from '../lib/cn'

function StatusRow({ label, ok, value }: { label: string; ok: boolean | null; value: string }) {
  return (
    <div className="flex items-center justify-between py-2.5">
      <dt className="text-muted">{label}</dt>
      <dd className="flex items-center gap-2">
        <span
          aria-hidden="true"
          className={cn('size-2 rounded-full', ok === null ? 'bg-faint' : ok ? 'bg-ok' : 'bg-danger')}
        />
        {value}
      </dd>
    </div>
  )
}

function ServiceStatus() {
  const { data, isPending, isError } = useQuery({ queryKey: ['health'], queryFn: getHealth })

  const apiOk = isPending ? null : !isError
  const dbOk = data ? data.database === 'ok' : isPending ? null : false

  return (
    <section aria-labelledby="status-heading" className="rounded-xl border border-line bg-surface p-5">
      <h2 id="status-heading" className="font-semibold">
        Service status
      </h2>
      <dl className="mt-2 divide-y divide-line text-sm">
        <StatusRow label="API" ok={apiOk} value={isPending ? 'Checking' : isError ? 'Unreachable' : 'Running'} />
        <StatusRow
          label="Database"
          ok={dbOk}
          value={isPending ? 'Checking' : dbOk ? 'Connected' : 'Unavailable'}
        />
        {data && <StatusRow label="Version" ok={null} value={data.version} />}
      </dl>
    </section>
  )
}

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-3xl font-semibold tracking-tight">Dashboard</h1>
      <p className="mt-2 text-muted">Your saved repositories and interview practice will appear here.</p>

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_20rem]">
        <section className="flex flex-col items-start rounded-xl border border-dashed border-line px-6 py-10 sm:px-8">
          <FolderGit2 size={28} strokeWidth={1.5} className="text-faint" aria-hidden="true" />
          <h2 className="mt-4 text-lg font-semibold">No repositories yet</h2>
          <p className="mt-1.5 max-w-md text-muted">
            Repository analysis isn't available yet. Once it is, repositories you add will be listed here with
            their analysis and interview progress.
          </p>
        </section>

        <ServiceStatus />
      </div>
    </div>
  )
}
