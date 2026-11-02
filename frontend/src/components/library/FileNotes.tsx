import { useNotes } from '../../hooks/useLibrary'
import NoteList, { NoteForm } from './NoteList'

/** Notes about one file, and a form for a new one about the highlighted line. */
export default function FileNotes({ repositoryId, path, line }: { repositoryId: string; path: string; line: number | null }) {
  const { data: notes = [] } = useNotes(repositoryId)
  const here = notes.filter((note) => note.path === path)

  return (
    <section aria-label="Notes on this file" className="border-t border-line pt-3">
      <h3 className="flex items-baseline justify-between text-sm font-medium">
        Notes
        <span className="text-xs font-normal text-faint">{here.length}</span>
      </h3>
      {here.length > 0 && (
        <div className="mt-2">
          <NoteList repositoryId={repositoryId} notes={here} />
        </div>
      )}
      <div className="mt-2.5">
        <NoteForm
          repositoryId={repositoryId}
          target={{ path, line }}
          compact
          placeholder={line ? `A note about line ${line}` : 'A note about this file (click a line number to pick a line)'}
        />
      </div>
    </section>
  )
}
