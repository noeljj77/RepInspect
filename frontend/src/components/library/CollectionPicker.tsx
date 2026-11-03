import { FolderPlus } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'

import { useCollections, useCreateCollection, useToggleCollection } from '../../hooks/useLibrary'

/** A menu of the person's collections, with a checkbox for this repository in each. */
export default function CollectionPicker({ repositoryId, memberOf }: { repositoryId: string; memberOf: string[] }) {
  const { data: collections = [] } = useCollections()
  const toggle = useToggleCollection(repositoryId)
  const create = useCreateCollection()
  const [name, setName] = useState('')
  const menu = useRef<HTMLDetailsElement>(null)

  useEffect(() => {
    // A <details> menu stays open until its summary is clicked again; close it on outside clicks too.
    function close(event: PointerEvent) {
      if (menu.current?.open && !menu.current.contains(event.target as Node)) menu.current.open = false
    }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [])

  function createAndAdd(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) return
    create.mutate(name.trim(), {
      onSuccess: (collection) => {
        setName('')
        toggle.mutate({ id: collection.id, member: true })
      },
    })
  }

  const names = collections.filter((c) => memberOf.includes(c.id)).map((c) => c.name)

  return (
    <details ref={menu} className="group relative">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 rounded-full border border-line px-2.5 py-0.5 text-xs text-muted hover:border-faint hover:text-ink">
        <FolderPlus size={12} aria-hidden="true" />
        {names.length === 0 ? 'Add to a collection' : names.join(', ')}
      </summary>
      <div className="absolute left-0 z-10 mt-1.5 w-64 rounded-lg border border-line bg-surface p-2 shadow-pop">
        {collections.length > 0 && (
          <fieldset>
            <legend className="sr-only">Collections</legend>
            {collections.map((collection) => (
              <label
                key={collection.id}
                className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-raised/60"
              >
                <input
                  type="checkbox"
                  checked={memberOf.includes(collection.id)}
                  disabled={toggle.isPending}
                  onChange={(event) => toggle.mutate({ id: collection.id, member: event.target.checked })}
                  className="accent-[var(--color-mark)]"
                />
                <span className="truncate">{collection.name}</span>
              </label>
            ))}
          </fieldset>
        )}
        <form onSubmit={createAndAdd} className={collections.length > 0 ? 'mt-1.5 border-t border-line pt-2' : ''}>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={80}
            aria-label="New collection name"
            placeholder="New collection, then Enter"
            className="h-8 w-full rounded-md border border-line bg-canvas px-2.5 text-sm placeholder:text-faint focus:border-mark focus:outline-none"
          />
        </form>
        {(create.isError || toggle.isError) && (
          <p role="alert" className="mt-1.5 px-1 text-xs text-danger">
            {(create.error ?? toggle.error)?.message}
          </p>
        )}
      </div>
    </details>
  )
}
