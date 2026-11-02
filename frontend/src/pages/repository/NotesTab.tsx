import NoteList, { NoteForm } from '../../components/library/NoteList'
import { useNotes } from '../../hooks/useLibrary'
import { useRepositoryContext } from '../../hooks/useRepositoryContext'

export default function NotesTab() {
  const { repository } = useRepositoryContext()
  const { data: notes, isPending, isError } = useNotes(repository.id)

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <section aria-labelledby="notes-heading" className="min-w-0 max-w-2xl">
        <h2 id="notes-heading" className="mb-4 font-semibold">
          Your notes
        </h2>
        {isPending ? (
          <p role="status" className="text-sm text-muted">
            Loading notes…
          </p>
        ) : isError ? (
          <p role="alert" className="text-sm text-danger">
            Your notes could not be loaded. Try refreshing the page.
          </p>
        ) : notes.length === 0 ? (
          <p className="text-sm text-muted">
            No notes yet. Write one here, or open a file and add a note about a specific line.
          </p>
        ) : (
          <NoteList repositoryId={repository.id} notes={notes} />
        )}
      </section>

      <aside aria-label="New note" className="self-start rounded-xl border border-line bg-surface p-4 lg:sticky lg:top-4">
        <h2 className="mb-2.5 text-sm font-medium">New note about this repository</h2>
        <NoteForm repositoryId={repository.id} />
        <p className="mt-3 text-xs text-muted">Notes stay when you refresh the repository, and only you can see them.</p>
      </aside>
    </div>
  )
}
