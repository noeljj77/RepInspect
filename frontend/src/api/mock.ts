import type { Citation, Finding } from './ai'
import { apiFetch, apiPost, apiSend } from './client'
import type { Category, Difficulty } from './interview'

export type Verdict = 'supported' | 'contradicted' | 'not_found' | 'unverified'

export interface ClaimCheck {
  claim: string
  /** "unverified": the grader's evidence did not check out. */
  verdict: Verdict
  citations: Citation[]
}

export interface Grade {
  score: number
  label: string
  summary: string
  strengths: string[]
  gaps: string[]
  claims: ClaimCheck[]
  /** Points a strong answer covers that this one did not, with their evidence. */
  missed_points: Finding[]
  follow_up: string | null
  removed_citations: number
}

export type TurnStatus = 'waiting' | 'grading' | 'graded' | 'skipped' | 'failed' | 'cancelled'

export interface Turn {
  id: string
  position: number
  kind: 'question' | 'follow_up'
  prompt: string
  category: Category
  difficulty: Difficulty
  status: TurnStatus
  answer: string | null
  score: number | null
  grade: Grade | null
  error_message: string | null
  asked_at: string | null
  answered_at: string | null
  graded_at: string | null
}

export interface Report {
  questions_answered: number
  skipped: number
  follow_ups_answered: number
  /** 0 to 4. */
  average_score: number | null
  percent: number | null
  follow_up_average: number | null
  by_category: Array<{ category: Category; label: string; average: number | null; count: number }>
  strengths: string[]
  gaps: string[]
  contradicted_claims: ClaimCheck[]
  files_to_review: string[]
}

export type InterviewStatus = 'preparing' | 'active' | 'completed' | 'failed'

export interface MockInterview {
  id: string
  status: InterviewStatus
  question_count: number
  /** Main questions asked so far (follow-ups not counted). */
  asked: number
  categories: Category[] | null
  difficulty: Difficulty | null
  report: Report | null
  error_message: string | null
  created_at: string
  completed_at: string | null
  turns: Turn[]
}

export interface InterviewSummary {
  id: string
  status: InterviewStatus
  question_count: number
  percent: number | null
  created_at: string
  completed_at: string | null
}

export interface StartRequest {
  question_count: number
  categories?: Category[] | null
  difficulty?: Difficulty | null
}

const base = (repositoryId: string) => `/api/repositories/${repositoryId}/mock-interviews`

export const listInterviews = (repositoryId: string) => apiFetch<InterviewSummary[]>(base(repositoryId))
export const getInterview = (repositoryId: string, id: string) => apiFetch<MockInterview>(`${base(repositoryId)}/${id}`)
export const startInterview = (repositoryId: string, request: StartRequest) =>
  apiPost<MockInterview>(base(repositoryId), request)
export const answerQuestion = (repositoryId: string, id: string, answer: string) =>
  apiPost<MockInterview>(`${base(repositoryId)}/${id}/answer`, { answer })
export const skipQuestion = (repositoryId: string, id: string) =>
  apiPost<MockInterview>(`${base(repositoryId)}/${id}/skip`)
export const retryGrading = (repositoryId: string, id: string, turnId: string) =>
  apiPost<MockInterview>(`${base(repositoryId)}/${id}/turns/${turnId}/retry`)
export const finishInterview = (repositoryId: string, id: string) =>
  apiPost<MockInterview>(`${base(repositoryId)}/${id}/finish`)
export const deleteInterview = (repositoryId: string, id: string) =>
  apiSend<void>('DELETE', `${base(repositoryId)}/${id}`)
