import { useOutletContext } from 'react-router'

import type { AnalysisDetail, RepositoryDetail } from '../api/repositories'

/** What the repository page shares with its tabs once the analysis has finished. */
export interface RepositoryContext {
  repository: RepositoryDetail
  analysis: AnalysisDetail
}

export const useRepositoryContext = () => useOutletContext<RepositoryContext>()
