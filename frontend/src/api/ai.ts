import { apiFetch, apiPost } from './client'

export type AiKind = 'overview' | 'technologies' | 'file' | 'report'

/** "missing" means nobody has asked for this explanation yet. */
export type AiStatus = 'missing' | 'pending' | 'completed' | 'failed'

/** A line range in a repository file, with the exact text the server found there. */
export interface Citation {
  path: string
  start_line: number
  end_line: number
  quote: string
}

export interface Finding {
  statement: string
  /** Only citations the server confirmed against the real file. */
  citations: Citation[]
  /** False when no citation could be confirmed: show it as inference. */
  verified: boolean
  /** Files the text mentions that do not exist in this repository. */
  ungrounded_paths: string[]
}

export interface OverviewSection {
  key: string
  title: string
  summary: string
  /** False when the analyzed files do not answer this part. */
  determined: boolean
  findings: Finding[]
  ungrounded_paths: string[]
}

export interface OverviewContent {
  sections: OverviewSection[]
  removed_citations: number
}

/** General knowledge about a technology. Nothing here is taken from the repository. */
export interface TechnologyExplanation {
  name: string
  what_it_is: string
  plausible_reason: string
  advantages: string[]
  alternatives: string[]
  trade_offs: string[]
}

export interface TechnologiesContent {
  technologies: TechnologyExplanation[]
}

export interface KeySymbol {
  name: string
  qualified_name: string
  kind: string
  start_line: number
  explanation: string
}

export interface FileExplanationContent {
  purpose: string
  determined: boolean
  inputs_outputs: string
  findings: Finding[]
  key_symbols: KeySymbol[]
  ungrounded_paths: string[]
  removed_citations: number
}

export interface Decision {
  /** The decision, backed by code when verified. */
  finding: Finding
  /** General knowledge, not taken from the repository. */
  alternatives: string[]
  trade_offs: string[]
}

/** A suggested next step: always an opinion. */
export interface Improvement {
  idea: string
  reason: string
}

/** Notes for talking about the project in an interview. */
export interface ReportContent {
  pitch: string
  problem: string
  walkthrough: Finding[]
  decisions: Decision[]
  highlights: Finding[]
  improvements: Improvement[]
  ungrounded_paths: string[]
  removed_citations: number
}

export interface ContentByKind {
  overview: OverviewContent
  technologies: TechnologiesContent
  file: FileExplanationContent
  report: ReportContent
}

export interface Explanation<K extends AiKind = AiKind> {
  id: string | null
  kind: K
  path: string | null
  status: AiStatus
  error_code: string | null
  error_message: string | null
  content: ContentByKind[K] | null
  model: string | null
  created_at: string | null
  completed_at: string | null
}

function aiUrl(repositoryId: string, kind: AiKind, path?: string): string {
  const url = `/api/repositories/${repositoryId}/ai/${kind}`
  return path === undefined ? url : `${url}?path=${encodeURIComponent(path)}`
}

export const getExplanation = <K extends AiKind>(repositoryId: string, kind: K, path?: string) =>
  apiFetch<Explanation<K>>(aiUrl(repositoryId, kind, path))

/** Start generating (or regenerating). The server answers at once with status "pending". */
export const requestExplanation = <K extends AiKind>(repositoryId: string, kind: K, path?: string) =>
  apiPost<Explanation<K>>(aiUrl(repositoryId, kind, path))
