import { Pencil, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'

import type { NewNote, Note } from '../../api/library'
import { useAddNote, useDeleteNote, useEditNote } from '../../hooks/useLibrary'
import { formatRelativeTime } from '../../lib/format'
import { fileLink } from '../../lib/links'
import { buttonClass } from '../ui/button'

const MAX_LENGTH = 5000

export function NoteForm({
  repositoryId,
  target,
  placeholder,
  compact,
}: {
  repositoryId: string
  /** The file and line new notes are about, if any. */
  target?: Pick<NewNote, 'path' | 'line'>
  placeholder?: string
  compact?: boolean
}) {
  const add = useAddNote(repositoryId)
  const [body, setBody] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!body.trim()) return
    add.mutate({ body: body.trim(), ...target }, { onSuccess: () => setBody('') })
  }

  return (
    <form onSubmit={submit}>
      <label className="sr-only" htmlFor={`note-${target?.path ?? 'repository'}`}>
        New note
      </label>
      <textarea
        id={`note-${target?.path ?? 'repository'}`}
        value={body}
        onChange={(event) => setBody(event.target.value)}
        rows={compact ? 2 : 3}
        maxLength={MAX_LENGTH}
        placeholder={placeholder ?? 'Write a note: something to remember, a question to prepare for…'}
        className="block w-full resize-y rounded-md border border-line bg-canvas px-3 py-2 text-sm leading-relaxed placeholder:text-faint focus:border-mark focus:outline-none"
      />
      <div className="mt-2 flex items-center justify-between gap-3">
        {add.isError ? (
          <p role="alert" className="text-xs text-danger">
            {add.error.message}
          </p>
        ) : (
          <span />
        )}
        <button type="submit" disabled={!body.trim() || add.isPending} className={buttonClass('secondary', 'h-8 px-3 text-xs')}>
          Save note
        </button>
      </div>
    </form>
  )
}

function NoteItem({ repositoryId, note, showPlace }: { repositoryId: string; note: Note; showPlace: boolean }) {
  const edit = useEditNote(repositoryId)
  const remove = useDeleteNote(repositoryId)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(note.body)
  const edited = note.updated_at !== note.created_at

  function save(event: FormEvent) {
    event.preventDefault()
    if (!draft.trim()) return
    edit.mutate({ id: note.id, body: draft.trim() }, { onSuccess: () => setEditing(false) })
  }

  return (
    <li className="border-t border-line py-3.5 first:border-t-0 first:pt-0">
      {showPlace && note.path && (
        <Link
          to={fileLink(repositoryId, note.path, note.line)}
          className="mb-1 inline-block font-mono text-[12px] text-mark hover:underline"
        >
          {note.path}
          {note.line ? `:${note.line}` : ''}
        </Link>
      )}
      {editing ? (
        <form onSubmit={save}>
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            rows={3}
            maxLength={MAX_LENGTH}
            aria-label="Edit note"
            autoFocus
            className="block w-full resize-y rounded-md border border-line bg-canvas px-3 py-2 text-sm leading-relaxed focus:border-mark focus:outline-none"
          />
          <div className="mt-2 flex gap-2">
            <button type="submit" disabled={edit.isPending} className={buttonClass('secondary', 'h-8 px-3 text-xs')}>
              Save
            </button>
            <button type="button" onClick={() => setEditing(false)} className={buttonClass('ghost', 'h-8 px-3 text-xs')}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{note.body}</p>
      )}
      <div className="mt-1.5 flex items-center gap-3 text-xs text-faint">
        <span>
          {edited ? 'Edited' : 'Written'} {formatRelativeTime(edited ? note.updated_at : note.created_at)}
        </span>
        {!editing && (
          <>
            <button
              type="button"
              onClick={() => {
                setDraft(note.body)
                setEditing(true)
              }}
              className="inline-flex items-center gap-1 hover:text-ink"
            >
              <Pencil size={11} aria-hidden="true" />
              Edit
            </button>
            <button
              type="button"
              onClick={() => remove.mutate(note.id)}
              disabled={remove.isPending}
              className="inline-flex items-center gap-1 hover:text-danger"
              aria-label="Delete note"
            >
              <Trash2 size={11} aria-hidden="true" />
              Delete
            </button>
          </>
        )}
      </div>
      {(edit.isError || remove.isError) && (
        <p role="alert" className="mt-1 text-xs text-danger">
          {(edit.error ?? remove.error)?.message}
        </p>
      )}
    </li>
  )
}

export default function NoteList({
  repositoryId,
  notes,
  showPlace = true,
}: {
  repositoryId: string
  notes: Note[]
  /** Show which file each note is about (off when the list is already about one file). */
  showPlace?: boolean
}) {
  return (
    <ul>
      {notes.map((note) => (
        <NoteItem key={note.id} repositoryId={repositoryId} note={note} showPlace={showPlace} />
      ))}
    </ul>
  )
}
