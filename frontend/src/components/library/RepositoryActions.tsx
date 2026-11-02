import { RefreshCw, Trash2, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { useNavigate } from 'react-router'

import { isInProgress, type RepositoryDetail } from '../../api/repositories'
import { useDeleteRepository, useStartAnalysis, useUploadNewVersion } from '../../hooks/useRepositories'
import { buttonClass } from '../ui/button'

/** Pick a .zip with a hidden file input, from a normal button. */
export function ZipPicker({
  onPick,
  disabled,
  label,
  variant = 'secondary',
}: {
  onPick: (file: File) => void
  disabled?: boolean
  label: string
  variant?: 'primary' | 'secondary' | 'ghost'
}) {
  const input = useRef<HTMLInputElement>(null)
  return (
    <>
      <input
        ref={input}
        type="file"
        accept=".zip,application/zip"
        aria-label={label}
        className="sr-only"
        tabIndex={-1}
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = '' // picking the same file again should still work
          if (file) onPick(file)
        }}
      />
      <button
        type="button"
        onClick={() => input.current?.click()}
        disabled={disabled}
        className={buttonClass(variant, 'h-9 px-3')}
      >
        <Upload size={15} aria-hidden="true" />
        {label}
      </button>
    </>
  )
}

export default function RepositoryActions({ repository }: { repository: RepositoryDetail }) {
  const refresh = useStartAnalysis(repository.id)
  const upload = useUploadNewVersion(repository.id)
  const remove = useDeleteRepository(repository.id)
  const navigate = useNavigate()
  const [confirming, setConfirming] = useState(false)
  const busy = isInProgress(repository.latest_analysis)
  const error = refresh.error ?? upload.error ?? remove.error

  return (
    <div className="flex flex-col items-start gap-2 sm:items-end">
      <div className="flex flex-wrap gap-2">
        {repository.source_type === 'zip' ? (
          <ZipPicker
            label="Upload new version"
            onPick={(file) => upload.mutate(file)}
            disabled={busy || upload.isPending}
          />
        ) : (
          <button
            type="button"
            onClick={() => refresh.mutate()}
            disabled={busy || refresh.isPending}
            className={buttonClass('secondary', 'h-9 px-3')}
            title="Analyze the latest commit again"
          >
            <RefreshCw size={15} aria-hidden="true" />
            Refresh
          </button>
        )}
        {confirming ? (
          <>
            <button
              type="button"
              onClick={() => remove.mutate(undefined, { onSuccess: () => navigate('/dashboard') })}
              disabled={remove.isPending}
              className={buttonClass('secondary', 'h-9 border-danger/50 px-3 text-danger hover:border-danger')}
            >
              Delete everything
            </button>
            <button type="button" onClick={() => setConfirming(false)} className={buttonClass('ghost', 'h-9 px-3')}>
              Keep it
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            disabled={busy}
            className={buttonClass('ghost', 'h-9 px-3')}
            title={busy ? 'Wait for the analysis to finish' : undefined}
          >
            <Trash2 size={15} aria-hidden="true" />
            Delete
          </button>
        )}
      </div>
      {confirming && (
        <p className="max-w-xs text-xs text-muted sm:text-right">
          Removes the repository, its versions, notes, explanations and conversations.
        </p>
      )}
      {error && (
        <p role="alert" className="max-w-xs text-sm text-danger sm:text-right">
          {error.message}
        </p>
      )}
    </div>
  )
}
