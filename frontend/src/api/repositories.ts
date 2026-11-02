import { apiFetch, apiPost } from './client'

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
  label: string | null
  created_at: string
}

export interface RepositorySummary extends RepositoryBase {
  description: string | null
  latest_analysis: AnalysisSummary | null
}

export interface RepositoryDetail extends RepositoryBase {
  latest_analysis: AnalysisDetail | null
  important_files: ImportantFile[]
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

export const listFiles = (id: string) => apiFetch<FileEntry[]>(`/api/repositories/${id}/files`)
export const readFile = (id: string, path: string) =>
  apiFetch<FileContent>(`/api/repositories/${id}/files/content?path=${encodeURIComponent(path)}`)
export const listDependencies = (id: string) =>
  apiFetch<Dependency[]>(`/api/repositories/${id}/dependencies`)
