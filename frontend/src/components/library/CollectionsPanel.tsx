import { Pencil, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import type { Collection } from '../../api/library'
import { useCollections, useCreateCollection, useDeleteCollection, useRenameCollection } from '../../hooks/useLibrary'
import { cn } from '../../lib/cn'

function CollectionRow({ collection, active }: { collection: Collection; active: boolean }) {
  const rename = useRenameCollection()
  const remove = useDeleteCollection()
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(collection.name)

  function save(event: FormEvent) {
    event.preventDefault()
    if (!name.trim() || name.trim() === collection.name) return setEditing(false)
    rename.mutate({ id: collection.id, name: name.trim() }, { onSuccess: () => setEditing(false) })
  }

  if (editing) {
    return (
      <li>
        <form onSubmit={save} className="py-1">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => event.key === 'Escape' && setEditing(false)}
            maxLength={80}
            autoFocus
            aria-label={`Rename ${collection.name}`}
            className="h-8 w-full rounded-md border border-line bg-canvas px-2.5 text-sm focus:border-mark focus:outline-none"
          />
        </form>
        {rename.isError && (
          <p role="alert" className="text-xs text-danger">
            {rename.error.message}
          </p>
        )}
      </li>
    )
  }

  return (
    <li className="group flex items-center gap-1">
      <Link
        to={active ? '?' : `?collection=${collection.id}`}
        aria-current={active ? 'true' : undefined}
        className={cn(
          'flex min-w-0 flex-1 items-baseline justify-between gap-2 rounded-md border-l-2 px-2 py-1.5 text-sm',
          active ? 'border-mark bg-raised/60 text-ink' : 'border-transparent text-muted hover:bg-raised/40 hover:text-ink',
        )}
      >
        <span className="truncate">{collection.name}</span>
        <span className="shrink-0 text-xs text-faint">{collection.repository_ids.length}</span>
      </Link>
      <button
        type="button"
        onClick={() => setEditing(true)}
        aria-label={`Rename ${collection.name}`}
        className="rounded p-1 text-faint opacity-0 group-hover:opacity-100 hover:text-ink focus-visible:opacity-100"
      >
        <Pencil size={12} aria-hidden="true" />
      </button>
      <button
        type="button"
        onClick={() => remove.mutate(collection.id)}
        disabled={remove.isPending}
        aria-label={`Delete collection ${collection.name}`}
        title="Delete the collection (its repositories stay in your library)"
        className="rounded p-1 text-faint opacity-0 group-hover:opacity-100 hover:text-danger focus-visible:opacity-100"
      >
        <Trash2 size={12} aria-hidden="true" />
      </button>
    </li>
  )
}

/** The person's collections on the dashboard. Choosing one filters the library list. */
export default function CollectionsPanel() {
  const { data: collections = [] } = useCollections()
  const create = useCreateCollection()
  const [params] = useSearchParams()
  const [name, setName] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) return
    create.mutate(name.trim(), { onSuccess: () => setName('') })
  }

  return (
    <section aria-labelledby="collections-heading" className="rounded-xl border border-line bg-surface p-5">
      <h2 id="collections-heading" className="font-semibold">
        Collections
      </h2>
      <p className="mt-1 text-sm text-muted">Group repositories, for example by interview or topic.</p>
      {collections.length > 0 && (
        <ul className="mt-3 space-y-0.5">
          {collections.map((collection) => (
            <CollectionRow key={collection.id} collection={collection} active={params.get('collection') === collection.id} />
          ))}
        </ul>
      )}
      <form onSubmit={submit} className="mt-3">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={80}
          aria-label="New collection name"
          placeholder="New collection, then Enter"
          className="h-9 w-full rounded-md border border-line bg-canvas px-3 text-sm placeholder:text-faint focus:border-mark focus:outline-none"
        />
      </form>
      {create.isError && (
        <p role="alert" className="mt-2 text-xs text-danger">
          {create.error.message}
        </p>
      )}
    </section>
  )
}
