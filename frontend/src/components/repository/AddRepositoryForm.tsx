import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'

import { buttonClass } from '../ui/button'
import { useAddRepository, useUploadZip } from '../../hooks/useRepositories'
import { ZipPicker } from '../library/RepositoryActions'

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
    <form onSubmit={handleSubmit} aria-labelledby="add-repository-heading">
      <h2 id="add-repository-heading" className="font-semibold">
        Analyze a repository
      </h2>
      <p className="mt-1 text-sm text-muted">
        Paste the link to a public GitHub repository, or upload a project as a .zip file (up to 50 MB).
      </p>

      <div className="mt-4 flex flex-col gap-3 sm:flex-row">
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
          className="h-10 min-w-0 flex-1 rounded-md border border-line bg-canvas px-3 font-mono text-[14px] placeholder:text-faint hover:border-faint focus:border-mark focus:outline-none focus:ring-1 focus:ring-mark"
        />
        <button type="submit" disabled={add.isPending} className={buttonClass('primary', 'sm:w-32')}>
          {add.isPending ? 'Adding…' : 'Analyze'}
        </button>
      </div>

      <div className="mt-3 flex items-center gap-3 text-sm text-muted">
        <span>or</span>
        <ZipPicker
          label={upload.isPending ? 'Uploading…' : 'Upload a ZIP'}
          onPick={(file) => upload.mutate(file, { onSuccess: open })}
          disabled={upload.isPending}
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
