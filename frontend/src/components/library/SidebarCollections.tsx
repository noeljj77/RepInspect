import { Pencil, Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router'

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
        <form onSubmit={save}>
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
          <p role="alert" className="px-2.5 text-xs text-danger">
            {rename.error.message}
          </p>
        )}
      </li>
    )
  }

  return (
    <li className="group flex items-center">
      <Link
        to={active ? '/dashboard' : `/dashboard?collection=${collection.id}`}
        aria-current={active ? 'true' : undefined}
        className={cn(
          'flex h-8 min-w-0 flex-1 items-center justify-between gap-2 rounded-md px-2.5 text-sm transition-colors',
          active ? 'bg-raised text-ink' : 'text-muted hover:bg-raised/50 hover:text-ink',
        )}
      >
        <span className="truncate">{collection.name}</span>
        <span className="shrink-0 text-xs text-faint tabular-nums">{collection.repository_ids.length}</span>
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

/** Collections in the sidebar. Choosing one filters the library on the dashboard. */
export default function SidebarCollections() {
  const { data: collections = [] } = useCollections()
  const create = useCreateCollection()
  const [params] = useSearchParams()
  const { pathname } = useLocation()
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const selected = pathname === '/dashboard' ? params.get('collection') : null

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) return setAdding(false)
    create.mutate(name.trim(), {
      onSuccess: () => {
        setName('')
        setAdding(false)
      },
    })
  }

  return (
    <section aria-labelledby="collections-heading">
      <div className="mb-1.5 flex items-center justify-between px-2.5">
        <h2 id="collections-heading" className="text-xs text-faint">
          Collections
        </h2>
        <button
          type="button"
          onClick={() => setAdding(true)}
          aria-label="New collection"
          title="New collection"
          className="rounded p-0.5 text-faint hover:text-ink"
        >
          <Plus size={14} aria-hidden="true" />
        </button>
      </div>
      {collections.length > 0 && (
        <ul className="space-y-px">
          {collections.map((collection) => (
            <CollectionRow key={collection.id} collection={collection} active={selected === collection.id} />
          ))}
        </ul>
      )}
      {(adding || collections.length === 0) && (
        <form onSubmit={submit} className="mt-1">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => event.key === 'Escape' && setAdding(false)}
            maxLength={80}
            autoFocus={adding}
            aria-label="New collection name"
            placeholder="New collection, then Enter"
            className="h-8 w-full rounded-md border border-line bg-canvas px-2.5 text-sm placeholder:text-faint focus:border-mark focus:outline-none"
          />
        </form>
      )}
      {create.isError && (
        <p role="alert" className="mt-1 px-2.5 text-xs text-danger">
          {create.error.message}
        </p>
      )}
    </section>
  )
}
