import { apiFetch, apiPost } from './client'

export type AnalysisStatus = 'queued' | 'fetching' | 'extracting' | 'completed' | 'failed'

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

export interface AnalysisDetail extends AnalysisSummary {
  github_metadata: GithubMetadata | null
  languages: Record<string, number> | null
  readme_path: string | null
  readme_text: string | null
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
}

export const IN_PROGRESS: AnalysisStatus[] = ['queued', 'fetching', 'extracting']

export const isInProgress = (analysis: { status: AnalysisStatus } | null | undefined) =>
  analysis != null && IN_PROGRESS.includes(analysis.status)

export const listRepositories = () => apiFetch<RepositorySummary[]>('/api/repositories')
export const getRepository = (id: string) => apiFetch<RepositoryDetail>(`/api/repositories/${id}`)
export const addRepository = (url: string) => apiPost<RepositoryDetail>('/api/repositories', { url })
export const startAnalysis = (id: string) =>
  apiPost<RepositoryDetail>(`/api/repositories/${id}/analyses`)
