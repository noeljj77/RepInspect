import { Plus, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { useUpdateLabels } from '../../hooks/useRepositories'

const MAX_LABELS = 10

/** The repository's labels as removable chips, with a field to add more. */
export default function LabelEditor({ repositoryId, labels }: { repositoryId: string; labels: string[] }) {
  const update = useUpdateLabels(repositoryId)
  const [adding, setAdding] = useState(false)
  const [draft, setDraft] = useState('')

  function add(event: FormEvent) {
    event.preventDefault()
    const label = draft.trim()
    if (!label) return setAdding(false)
    update.mutate([...labels, label], { onSuccess: () => setDraft('') })
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5" aria-label="Labels" role="group">
      {labels.map((label) => (
        <span
          key={label}
          className="inline-flex items-center gap-1 rounded-full border border-line bg-raised/60 py-0.5 pr-1 pl-2.5 text-xs"
        >
          {label}
          <button
            type="button"
            onClick={() => update.mutate(labels.filter((l) => l !== label))}
            disabled={update.isPending}
            aria-label={`Remove label ${label}`}
            className="rounded-full p-0.5 text-faint hover:bg-line hover:text-ink"
          >
            <X size={11} aria-hidden="true" />
          </button>
        </span>
      ))}

      {adding ? (
        <form onSubmit={add} className="inline-flex">
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={() => !draft.trim() && setAdding(false)}
            onKeyDown={(event) => event.key === 'Escape' && setAdding(false)}
            maxLength={40}
            autoFocus
            aria-label="New label"
            placeholder="Label, then Enter"
            className="h-6 w-36 rounded-full border border-line bg-canvas px-2.5 text-xs placeholder:text-faint focus:border-mark focus:outline-none"
          />
        </form>
      ) : (
        labels.length < MAX_LABELS && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="inline-flex items-center gap-1 rounded-full border border-dashed border-line px-2.5 py-0.5 text-xs text-muted hover:border-faint hover:text-ink"
          >
            <Plus size={11} aria-hidden="true" />
            {labels.length === 0 ? 'Add a label' : 'Label'}
          </button>
        )
      )}
      {update.isError && (
        <span role="alert" className="text-xs text-danger">
          {update.error.message}
        </span>
      )}
    </div>
  )
}
