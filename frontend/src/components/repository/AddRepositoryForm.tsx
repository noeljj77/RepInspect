import { Link as LinkIcon } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'

import { useAddRepository, useUploadZip } from '../../hooks/useRepositories'
import { ZipPicker } from '../library/RepositoryActions'
import { buttonClass } from '../ui/button'

/** One bar: paste a GitHub link, or upload a ZIP instead. */
export default function AddRepositoryForm() {
  const [url, setUrl] = useState('')
  const add = useAddRepository()
  const upload = useUploadZip()
  const navigate = useNavigate()
  const open = (repository: { id: string }) => navigate(`/repositories/${repository.id}`)

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    add.mutate(url.trim(), { onSuccess: open })
  }

  return (
    <form
      onSubmit={handleSubmit}
      aria-labelledby="add-repository-heading"
      className="rounded-xl border border-line bg-surface p-4 sm:p-5"
    >
      <h2 id="add-repository-heading" className="sr-only">
        Analyze a repository
      </h2>
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative min-w-0 flex-1">
          <LinkIcon
            size={16}
            className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-faint"
            aria-hidden="true"
          />
          <input
            type="text"
            inputMode="url"
            name="url"
            aria-label="GitHub repository URL"
            placeholder="https://github.com/owner/repository"
            autoComplete="off"
            spellCheck={false}
            required
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            className="h-10 w-full rounded-md border border-line bg-canvas pr-3 pl-9 font-mono text-[14px] placeholder:text-faint hover:border-faint focus:border-mark focus:ring-1 focus:ring-mark focus:outline-none"
          />
        </div>
        <button type="submit" disabled={add.isPending} className={buttonClass('primary', 'sm:w-32')}>
          {add.isPending ? 'Adding…' : 'Analyze'}
        </button>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted">
        <span>Not on GitHub, or not public? Upload the project as a ZIP:</span>
        <ZipPicker
          label={upload.isPending ? 'Uploading…' : 'Upload a ZIP'}
          onPick={(file) => upload.mutate(file, { onSuccess: open })}
          disabled={upload.isPending}
          variant="ghost"
        />
      </div>

      {(add.isError || upload.isError) && (
        <p role="alert" className="mt-3 text-sm text-danger">
          {(add.error ?? upload.error)?.message}
        </p>
      )}
    </form>
  )
}
