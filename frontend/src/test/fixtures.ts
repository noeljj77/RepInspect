import type {
  AnalysisDetail,
  AnalysisSummary,
  RepositoryDetail,
  RepositorySummary,
} from '../api/repositories'

export const REPO_ID = '22222222-2222-2222-2222-222222222222'

export function analysis(overrides: Partial<AnalysisDetail> = {}): AnalysisDetail {
  return {
    id: '33333333-3333-3333-3333-333333333333',
    version: 1,
    status: 'completed',
    error_code: null,
    error_message: null,
    commit_sha: '1234567890abcdef1234567890abcdef12345678',
    file_count: 12,
    total_bytes: 20480,
    skipped_summary: null,
    redaction_count: 0,
    truncated: false,
    created_at: '2026-11-02T10:00:00Z',
    completed_at: '2026-11-02T10:00:20Z',
    github_metadata: {
      full_name: 'pallets/flask',
      description: 'The Python micro framework for building web applications.',
      html_url: 'https://github.com/pallets/flask',
      homepage: null,
      default_branch: 'main',
      stars: 68500,
      forks: 16200,
      open_issues: 21,
      created_at: '2010-04-06T00:00:00Z',
      updated_at: '2026-10-30T00:00:00Z',
      pushed_at: '2026-10-30T00:00:00Z',
      license: 'BSD-3-Clause',
      topics: [],
      size_kb: 9000,
      archived: false,
      fork: false,
    },
    languages: { Python: 900, HTML: 100 },
    readme_path: 'README.md',
    readme_text: '# Flask\n\nA small web framework.',
    ...overrides,
  }
}

export function repositoryDetail(
  analysisOverrides: Partial<AnalysisDetail> | null = {},
): RepositoryDetail {
  return {
    id: REPO_ID,
    source_type: 'github',
    source_url: 'https://github.com/pallets/flask',
    owner: 'pallets',
    name: 'flask',
    label: null,
    created_at: '2026-11-02T10:00:00Z',
    latest_analysis: analysisOverrides === null ? null : analysis(analysisOverrides),
  }
}

/** The slim version of an analysis that the repository list endpoint returns. */
export function analysisSummary(overrides: Partial<AnalysisSummary> = {}): AnalysisSummary {
  const full = analysis()
  return {
    id: full.id,
    version: full.version,
    status: full.status,
    error_code: full.error_code,
    error_message: full.error_message,
    commit_sha: full.commit_sha,
    file_count: full.file_count,
    total_bytes: full.total_bytes,
    skipped_summary: full.skipped_summary,
    redaction_count: full.redaction_count,
    truncated: full.truncated,
    created_at: full.created_at,
    completed_at: full.completed_at,
    ...overrides,
  }
}

export function repositorySummary(overrides: Partial<RepositorySummary> = {}): RepositorySummary {
  return {
    id: REPO_ID,
    source_type: 'github',
    source_url: 'https://github.com/pallets/flask',
    owner: 'pallets',
    name: 'flask',
    label: null,
    description: 'The Python micro framework',
    created_at: '2026-11-02T10:00:00Z',
    latest_analysis: analysisSummary(),
    ...overrides,
  }
}
