import { useSearchParams } from 'react-router'

import FileTree from '../../components/repository/FileTree'
import FileViewer from '../../components/repository/FileViewer'
import { useFiles } from '../../hooks/useRepositories'
import { useRepositoryContext } from '../../hooks/useRepositoryContext'

function parseLine(value: string | null): number | null {
  const line = Number(value)
  return Number.isInteger(line) && line > 0 ? line : null
}

export default function FilesTab() {
  const { repository } = useRepositoryContext()
  const { data: files, isPending, isError } = useFiles(repository.id)
  const [params, setParams] = useSearchParams()

  const path = params.get('path')
  const line = parseLine(params.get('line'))

  function selectLine(next: number) {
    // `replace` so highlighting lines does not fill the browser history.
    setParams({ path: path ?? '', line: String(next) }, { replace: true })
  }

  if (isPending) {
    return (
      <p role="status" className="text-sm text-muted">
        Loading files…
      </p>
    )
  }
  if (isError) {
    return (
      <p role="alert" className="text-sm text-danger">
        The file list could not be loaded. Try refreshing the page.
      </p>
    )
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[17rem_minmax(0,1fr)]">
      <div className="lg:sticky lg:top-4 lg:max-h-[calc(100dvh-2rem)] lg:self-start lg:overflow-hidden">
        <div className="flex max-h-[50vh] flex-col lg:max-h-[calc(100dvh-2rem)]">
          <FileTree repositoryId={repository.id} files={files} selectedPath={path} />
        </div>
      </div>

      <div className="min-w-0">
        {path ? (
          <FileViewer repositoryId={repository.id} path={path} line={line} onSelectLine={selectLine} />
        ) : (
          <div className="rounded-xl border border-dashed border-line px-6 py-10">
            <h2 className="font-semibold">Pick a file</h2>
            <p className="mt-1.5 max-w-md text-sm text-muted">
              Choose a file from the list to read it, see its functions and classes, and follow its imports to
              other files. Files marked with an amber dot are the ones worth reading first.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
