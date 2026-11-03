import { Ellipsis, RefreshCw, Trash2, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
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
  const menu = useRef<HTMLDetailsElement>(null)
  const busy = isInProgress(repository.latest_analysis)
  const error = refresh.error ?? upload.error ?? remove.error

  useEffect(() => {
    // A <details> menu stays open until its summary is clicked again; close it on outside clicks too.
    function close(event: PointerEvent) {
      if (menu.current?.open && !menu.current.contains(event.target as Node)) menu.current.open = false
    }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [])

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
        <details ref={menu} className="relative" onToggle={(event) => !event.currentTarget.open && setConfirming(false)}>
          <summary
            aria-label="More"
            className={buttonClass('ghost', 'h-9 cursor-pointer list-none px-2.5 [&::-webkit-details-marker]:hidden')}
          >
            <Ellipsis size={17} aria-hidden="true" />
          </summary>
          <div className="absolute right-0 z-20 mt-1.5 w-64 rounded-lg border border-line bg-surface p-2 shadow-[0_12px_30px_-12px_rgba(0,0,0,0.6)]">
            {confirming ? (
              <div className="space-y-2 p-1">
                <p className="text-xs text-muted">
                  Removes the repository, its versions, notes, explanations and conversations.
                </p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => remove.mutate(undefined, { onSuccess: () => navigate('/dashboard') })}
                    disabled={remove.isPending}
                    className={buttonClass('secondary', 'h-9 border-danger/50 px-3 text-danger hover:border-danger')}
                  >
                    Delete everything
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirming(false)}
                    className={buttonClass('ghost', 'h-9 px-3')}
                  >
                    Keep it
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirming(true)}
                disabled={busy}
                title={busy ? 'Wait for the analysis to finish' : undefined}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm text-danger hover:bg-raised/60 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Trash2 size={15} aria-hidden="true" />
                Delete
              </button>
            )}
          </div>
        </details>
      </div>
      {error && (
        <p role="alert" className="max-w-xs text-sm text-danger sm:text-right">
          {error.message}
        </p>
      )}
    </div>
  )
}
