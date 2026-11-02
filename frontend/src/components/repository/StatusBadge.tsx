import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react'

import type { AnalysisStatus } from '../../api/repositories'
import { cn } from '../../lib/cn'

const labels: Record<AnalysisStatus, string> = {
  queued: 'Queued',
  fetching: 'Downloading',
  extracting: 'Reading files',
  completed: 'Ready',
  failed: 'Failed',
}

export default function StatusBadge({ status }: { status: AnalysisStatus }) {
  const working = status === 'queued' || status === 'fetching' || status === 'extracting'
  const Icon = status === 'completed' ? CheckCircle2 : status === 'failed' ? AlertCircle : Loader2

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        status === 'completed' && 'border-ok/30 text-ok',
        status === 'failed' && 'border-danger/30 text-danger',
        working && 'border-mark/30 text-mark',
      )}
    >
      <Icon size={13} strokeWidth={2} className={cn(working && 'animate-spin')} aria-hidden="true" />
      {labels[status]}
    </span>
  )
}
