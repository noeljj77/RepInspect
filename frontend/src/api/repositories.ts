import { ApiError, apiFetch, apiPost, apiSend } from './client'

export type AnalysisStatus =
  | 'queued'
  | 'fetching'
  | 'extracting'
  | 'analyzing'
  | 'completed'
  | 'failed'

export interface AnalysisSummary {
  id: string
  version: number
  status: AnalysisStatus
  error_code: string | null
  error_message: string | null
  commit_sha: string | null
  file_count: number
  total_bytes: number
  skipped_summary: Record<string, number> | null
  redaction_count: number
  truncated: boolean
  /** A newer version replaced this one and its stored files were deleted. */
  source_removed: boolean
  created_at: string
  completed_at: string | null
}

export interface GithubMetadata {
  full_name: string
  description: string | null
  html_url: string
  homepage: string | null
  default_branch: string
  stars: number
  forks: number
  open_issues: number
  created_at: string | null
  updated_at: string | null
  pushed_at: string | null
  license: string | null
  topics: string[]
  size_kb: number
  archived: boolean
  fork: boolean
}

export interface Evidence {
  kind: 'dependency' | 'import' | 'file'
  path: string
  line: number | null
  detail: string
  /** For dependencies: runtime, dev, optional... Absent in older analyses. */
  scope?: string | null
}

export interface Technology {
  name: string
  category: string
  evidence: Evidence[]
  /** Only a development dependency, used only from tests. Absent in older analyses. */
  dev_only?: boolean
}

export interface LanguageStat {
  name: string
  files: number
  lines: number
  bytes: number
  is_programming: boolean
}

export interface CodeStats {
  languages: LanguageStat[]
  totals: {
    files: number
    code_lines: number
    symbols: number
    symbols_by_kind: Record<string, number>
    imports: number
    internal_imports: number
    dependencies: number
    test_files: number
    parse_errors: number
  }
}

export interface AnalysisDetail extends AnalysisSummary {
  github_metadata: GithubMetadata | null
  languages: Record<string, number> | null
  /** null when code analysis was not available for this import. */
  technologies: Technology[] | null
  code_stats: CodeStats | null
  readme_path: string | null
  readme_text: string | null
}

export interface ImportantFile {
  path: string
  language: string | null
  score: number
  reasons: string[]
}

interface RepositoryBase {
  id: string
  source_type: 'github' | 'zip'
  source_url: string | null
  owner: string | null
  name: string
  labels: string[]
  collection_ids: string[]
  created_at: string
}

export interface RepositorySummary extends RepositoryBase {
  description: string | null
  latest_analysis: AnalysisSummary | null
  /** The main languages by lines of code (share from 0 to 1), for the library list. */
  languages: Array<{ name: string; share: number }>
  code_lines: number | null
}

export interface RepositoryDetail extends RepositoryBase {
  /** The newest version, whatever its status: it may be a refresh still running. */
  latest_analysis: AnalysisDetail | null
  /** The newest version that finished: what the page shows. */
  current_analysis: AnalysisDetail | null
  important_files: ImportantFile[]
}

export interface PathChanges {
  count: number
  /** The first 100, sorted. */
  paths: string[]
}

export interface Changes {
  added: PathChanges
  removed: PathChanges
  modified: PathChanges
  unchanged: number
  /** False when an older version predates content hashes, so changes are judged by size. */
  exact: boolean
  technologies_added: string[]
  technologies_removed: string[]
  dependencies_added: string[]
  dependencies_removed: string[]
  dependencies_changed: string[]
}

export interface VersionChanges {
  version: number
  previous_version: number | null
  previous_commit_sha: string | null
  changes: Changes | null
}

export interface FileEntry {
  path: string
  language: string | null
  size_bytes: number
  line_count: number | null
  /** null for stored files; otherwise why the file was left out. */
  skipped_reason: string | null
  importance_score: number
  symbol_count: number
  parse_error: boolean
}

export interface CodeSymbol {
  kind: string
  name: string
  qualified_name: string
  start_line: number
  end_line: number
  signature: string
  doc: string | null
  decorators: string[] | null
}

export interface CodeImport {
  module: string
  names: string[]
  line: number
  resolved_path: string | null
}

export interface FileContent {
  path: string
  language: string | null
  size_bytes: number
  line_count: number | null
  content: string
  parse_error: boolean
  importance_reasons: string[]
  symbols: CodeSymbol[]
  imports: CodeImport[]
  imported_by: string[]
}

export interface Dependency {
  ecosystem: 'pypi' | 'npm' | 'maven'
  name: string
  version_spec: string | null
  scope: string
  source_file: string
  line: number | null
}

export const IN_PROGRESS: AnalysisStatus[] = ['queued', 'fetching', 'extracting', 'analyzing']

export const isInProgress = (analysis: { status: AnalysisStatus } | null | undefined) =>
  analysis != null && IN_PROGRESS.includes(analysis.status)

export const listRepositories = () => apiFetch<RepositorySummary[]>('/api/repositories')
export const getRepository = (id: string) => apiFetch<RepositoryDetail>(`/api/repositories/${id}`)
export const addRepository = (url: string) => apiPost<RepositoryDetail>('/api/repositories', { url })
export const startAnalysis = (id: string) =>
  apiPost<RepositoryDetail>(`/api/repositories/${id}/analyses`)

export const updateLabels = (id: string, labels: string[]) =>
  apiSend<RepositoryDetail>('PATCH', `/api/repositories/${id}`, { labels })
export const deleteRepository = (id: string) => apiSend<void>('DELETE', `/api/repositories/${id}`)

/** Matches the server's MAX_UPLOAD_BYTES. */
export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024

/** The file is sent as the raw request body, which lets the server stop an oversized upload early. */
function sendZip(url: string, file: File) {
  // Checked here too: a browser shows a refused oversized upload as a network error, not the message.
  if (file.size > MAX_UPLOAD_BYTES) {
    return Promise.reject(
      new ApiError(413, `The file is larger than the ${MAX_UPLOAD_BYTES / (1024 * 1024)} MB upload limit.`, null),
    )
  }
  return apiFetch<RepositoryDetail>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/zip' },
    body: file,
  })
}
export const uploadZip = (file: File) =>
  sendZip(`/api/repositories/upload?name=${encodeURIComponent(file.name)}`, file)
export const uploadNewVersion = (id: string, file: File) => sendZip(`/api/repositories/${id}/upload`, file)

export const listVersions = (id: string) => apiFetch<AnalysisSummary[]>(`/api/repositories/${id}/analyses`)
export const versionChanges = (id: string, analysisId: string) =>
  apiFetch<VersionChanges>(`/api/repositories/${id}/analyses/${analysisId}/changes`)

export const listFiles = (id: string) => apiFetch<FileEntry[]>(`/api/repositories/${id}/files`)
export const readFile = (id: string, path: string) =>
  apiFetch<FileContent>(`/api/repositories/${id}/files/content?path=${encodeURIComponent(path)}`)
export const listDependencies = (id: string) =>
  apiFetch<Dependency[]>(`/api/repositories/${id}/dependencies`)
