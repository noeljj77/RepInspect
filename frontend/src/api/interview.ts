import type { Finding } from './ai'
import { apiFetch, apiPost, apiSend } from './client'

export type Category =
  | 'architecture'
  | 'implementation'
  | 'technologies'
  | 'data'
  | 'testing'
  | 'security'
  | 'performance'
  | 'trade_offs'

export const CATEGORY_LABELS: Record<Category, string> = {
  architecture: 'Architecture',
  implementation: 'Implementation',
  technologies: 'Technology choices',
  data: 'Data and storage',
  testing: 'Testing and quality',
  security: 'Security',
  performance: 'Performance and scaling',
  trade_offs: 'Trade-offs and improvements',
}

export type Difficulty = 'basic' | 'intermediate' | 'advanced'
export type Progress = 'new' | 'practicing' | 'confident'

export interface Question {
  id: string
  /** The version the question was written from. */
  analysis_version: number
  category: Category
  difficulty: Difficulty
  question: string
  why_asked: string
  /** Points a strong answer covers, checked against the code. */
  answer_points: Finding[]
  follow_ups: string[]
  /** False when no answer point could be confirmed: the suggested answer is a guess. */
  grounded: boolean
  removed_citations: number
  status: Progress
  user_answer: string | null
  practiced_at: string | null
  created_at: string
}

export interface Batch {
  id: string
  status: 'pending' | 'completed' | 'failed'
  requested_count: number
  question_count: number
  error_code: string | null
  error_message: string | null
  created_at: string
  completed_at: string | null
}

export interface Questions {
  questions: Question[]
  latest_batch: Batch | null
  progress: Record<Progress, number>
}

export interface GenerateRequest {
  count: number
  categories?: Category[] | null
  difficulty?: Difficulty | null
}

const url = (repositoryId: string) => `/api/repositories/${repositoryId}/questions`

export const getQuestions = (repositoryId: string) => apiFetch<Questions>(url(repositoryId))
export const generateQuestions = (repositoryId: string, request: GenerateRequest) =>
  apiPost<Questions>(url(repositoryId), request)
export const updateQuestion = (
  repositoryId: string,
  questionId: string,
  change: { status?: Progress; user_answer?: string | null },
) => apiSend<Question>('PATCH', `${url(repositoryId)}/${questionId}`, change)
export const deleteQuestion = (repositoryId: string, questionId: string) =>
  apiSend<void>('DELETE', `${url(repositoryId)}/${questionId}`)
