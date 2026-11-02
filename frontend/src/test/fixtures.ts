import type {
  AiKind,
  ContentByKind,
  Explanation,
  FileExplanationContent,
  OverviewContent,
  TechnologiesContent,
} from '../api/ai'
import type {
  AnalysisDetail,
  AnalysisSummary,
  Dependency,
  FileContent,
  FileEntry,
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
    technologies: [
      {
        name: 'Flask',
        category: 'Backend framework',
        evidence: [
          { kind: 'dependency', path: 'pyproject.toml', line: 12, detail: 'flask >=3.0' },
          { kind: 'import', path: 'src/flask/app.py', line: 3, detail: 'import flask' },
        ],
      },
      {
        name: 'pytest',
        category: 'Testing',
        evidence: [{ kind: 'file', path: 'pytest.ini', line: null, detail: 'pytest.ini' }],
      },
    ],
    code_stats: {
      languages: [
        { name: 'Python', files: 40, lines: 9000, bytes: 300000, is_programming: true },
        { name: 'Markdown', files: 5, lines: 800, bytes: 20000, is_programming: false },
      ],
      totals: {
        files: 12,
        code_lines: 9000,
        symbols: 300,
        symbols_by_kind: { function: 120, method: 150, class: 25, interface: 0, enum: 0, type: 5 },
        imports: 200,
        internal_imports: 90,
        dependencies: 7,
        test_files: 4,
        parse_errors: 0,
      },
    },
    readme_path: 'README.md',
    readme_text: '# Flask\n\nA small web framework.',
    ...overrides,
  }
}

export function repositoryDetail(
  analysisOverrides: Partial<AnalysisDetail> | null = {},
  overrides: Partial<RepositoryDetail> = {},
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
    important_files: [
      { path: 'README.md', language: 'Markdown', score: 50, reasons: ['Project README'] },
      {
        path: 'src/flask/app.py',
        language: 'Python',
        score: 45,
        reasons: ['Application entry point', 'Imported by 12 files'],
      },
    ],
    ...overrides,
  }
}

export function fileEntry(overrides: Partial<FileEntry> = {}): FileEntry {
  return {
    path: 'src/flask/app.py',
    language: 'Python',
    size_bytes: 1200,
    line_count: 40,
    skipped_reason: null,
    importance_score: 0,
    symbol_count: 0,
    parse_error: false,
    ...overrides,
  }
}

export function fileContent(overrides: Partial<FileContent> = {}): FileContent {
  return {
    path: 'src/flask/app.py',
    language: 'Python',
    size_bytes: 1200,
    line_count: 6,
    content: 'import os\nfrom .helpers import url_for\n\n\nclass Flask:\n    def run(self): ...\n',
    parse_error: false,
    importance_reasons: ['Application entry point'],
    symbols: [
      {
        kind: 'class',
        name: 'Flask',
        qualified_name: 'Flask',
        start_line: 5,
        end_line: 6,
        signature: 'class Flask',
        doc: null,
        decorators: null,
      },
      {
        kind: 'method',
        name: 'run',
        qualified_name: 'Flask.run',
        start_line: 6,
        end_line: 6,
        signature: 'def run(self)',
        doc: null,
        decorators: null,
      },
    ],
    imports: [
      { module: 'os', names: [], line: 1, resolved_path: null },
      { module: '.helpers', names: ['url_for'], line: 2, resolved_path: 'src/flask/helpers.py' },
    ],
    imported_by: ['src/flask/__init__.py', 'tests/test_app.py'],
    ...overrides,
  }
}

export function dependency(overrides: Partial<Dependency> = {}): Dependency {
  return {
    ecosystem: 'pypi',
    name: 'flask',
    version_spec: '>=3.0',
    scope: 'runtime',
    source_file: 'pyproject.toml',
    line: 12,
    ...overrides,
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

export function explanation<K extends AiKind>(
  kind: K,
  content: ContentByKind[K] | null,
  overrides: Partial<Explanation<K>> = {},
): Explanation<K> {
  return {
    id: '44444444-4444-4444-4444-444444444444',
    kind,
    path: null,
    status: content ? 'completed' : 'pending',
    error_code: null,
    error_message: null,
    content,
    model: 'gemini-test',
    created_at: '2026-11-02T10:01:00Z',
    completed_at: content ? '2026-11-02T10:01:10Z' : null,
    ...overrides,
  }
}

export function overviewContent(): OverviewContent {
  return {
    removed_citations: 1,
    sections: [
      {
        key: 'purpose',
        title: 'What the project does',
        summary: 'Flask is a small framework for web applications.',
        determined: true,
        ungrounded_paths: [],
        findings: [
          {
            statement: 'The application object is the Flask class.',
            verified: true,
            ungrounded_paths: [],
            citations: [{ path: 'src/flask/app.py', start_line: 5, end_line: 5, quote: 'class Flask:' }],
          },
          {
            statement: 'It is probably used for small services.',
            verified: false,
            ungrounded_paths: ['server/main.py'],
            citations: [],
          },
        ],
      },
      {
        key: 'frontend',
        title: 'Frontend structure',
        summary: '',
        determined: false,
        ungrounded_paths: [],
        findings: [],
      },
    ],
  }
}

export function technologiesContent(): TechnologiesContent {
  return {
    technologies: [
      {
        name: 'flask',
        what_it_is: 'A lightweight Python web framework.',
        plausible_reason: 'It keeps small apps simple.',
        advantages: ['Small core'],
        alternatives: ['Django', 'FastAPI'],
        trade_offs: ['Fewer built-in features'],
      },
    ],
  }
}

export function fileExplanationContent(): FileExplanationContent {
  return {
    purpose: 'Defines the central application class.',
    determined: true,
    inputs_outputs: 'Takes configuration, serves requests.',
    findings: [],
    key_symbols: [
      {
        name: 'Flask',
        qualified_name: 'Flask',
        kind: 'class',
        start_line: 5,
        explanation: 'The application object.',
      },
    ],
    ungrounded_paths: [],
    removed_citations: 0,
  }
}
