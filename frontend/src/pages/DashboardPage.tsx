import { useQuery } from '@tanstack/react-query'

import { getHealth } from '../api/health'
import AddRepositoryForm from '../components/repository/AddRepositoryForm'
import RepositoryList from '../components/repository/RepositoryList'
import { useCurrentUser } from '../hooks/useAuth'
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
    <section aria-labelledby="status-heading" className="self-start rounded-xl border border-line bg-surface p-5">
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
  const { data: user } = useCurrentUser()

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-3xl font-semibold tracking-tight">Welcome, {user?.display_name}</h1>
      <p className="mt-2 text-muted">Analyze a repository, then explore it and prepare to talk about it.</p>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_18rem]">
        <div className="min-w-0 space-y-10">
          <section className="rounded-xl border border-line bg-surface p-5">
            <AddRepositoryForm />
          </section>

          <section aria-labelledby="library-heading">
            <h2 id="library-heading" className="mb-4 font-semibold">
              Your repositories
            </h2>
            <RepositoryList />
          </section>
        </div>

        <ServiceStatus />
      </div>
    </div>
  )
}
