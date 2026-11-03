import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ada, mockApi, type ApiRoutes } from '../test/mockApi'
import { dependency, REPO_ID, repositoryDetail } from '../test/fixtures'
import { renderRoute } from '../test/renderRoute'

const base = `/api/repositories/${REPO_ID}`

function open(url: string, detail = repositoryDetail(), extra: ApiRoutes = {}) {
  mockApi({
    'GET /api/auth/me': { body: ada },
    [`GET ${base}`]: { body: detail },
    [`GET ${base}/files`]: { body: [] },
    ...extra,
  })
  return renderRoute(url)
}

describe('repository tabs', () => {
  it('shows Overview, Files and Dependencies with counts once the analysis is ready', async () => {
    open(`/repositories/${REPO_ID}`)

    const tabs = await screen.findByRole('navigation', { name: 'Repository sections' })
    expect(within(tabs).getByRole('link', { name: 'Overview' })).toHaveAttribute('aria-current', 'page')
    expect(within(tabs).getByRole('link', { name: 'Files 12' })).toHaveAttribute('href', `/repositories/${REPO_ID}/files`)
    expect(within(tabs).getByRole('link', { name: 'Dependencies 7' })).toBeInTheDocument()
  })

  it('moves between tabs', async () => {
    const user = userEvent.setup()
    const { router } = open(`/repositories/${REPO_ID}`, repositoryDetail(), {
      [`GET ${base}/dependencies`]: { body: [dependency()] },
    })

    await user.click(await screen.findByRole('link', { name: 'Dependencies 7' }))

    expect(router.state.location.pathname).toBe(`/repositories/${REPO_ID}/dependencies`)
    expect(await screen.findByRole('region', { name: 'pyproject.toml' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Dependencies 7' })).toHaveAttribute('aria-current', 'page')
  })

  it('shows no tabs while the analysis is still running', async () => {
    open(`/repositories/${REPO_ID}`, repositoryDetail({ status: 'analyzing' }))

    expect(await screen.findByRole('region', { name: 'Analysis progress' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Repository sections' })).not.toBeInTheDocument()
  })

  it('shows the analyzing step in the progress list', async () => {
    open(`/repositories/${REPO_ID}`, repositoryDetail({ status: 'analyzing' }))

    const progress = await screen.findByRole('region', { name: 'Analysis progress' })
    expect(within(progress).getByText('Analyzing code').closest('li')).toHaveAttribute('aria-current', 'step')
    expect(within(progress).getByText('Reading files').closest('li')).not.toHaveAttribute('aria-current')
  })

  it('does not show file tabs when the analysis failed', async () => {
    open(`/repositories/${REPO_ID}`, repositoryDetail({ status: 'failed', error_message: 'Nope.' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Nope.')
    expect(screen.queryByRole('navigation', { name: 'Repository sections' })).not.toBeInTheDocument()
  })
})

describe('Overview tab', () => {
  it('shows statistics, including combined totals', async () => {
    open(`/repositories/${REPO_ID}`)

    const stats = await screen.findByRole('region', { name: 'Statistics' })
    const value = (label: string) => within(stats).getByText(label).nextElementSibling?.textContent
    expect(value('Lines of code')).toBe('9,000')
    expect(value('Functions and methods')).toBe('270') // 120 functions + 150 methods
    expect(value('Classes and types')).toBe('30') // 25 classes + 5 type aliases
    expect(value('Dependencies')).toBe('7')
    expect(value('Test files')).toBe('4')
    expect(stats).toHaveTextContent('90 of 200 imports link one file in this repository to another')
  })

  it('mentions files the parser could not fully read', async () => {
    const stats = repositoryDetail().latest_analysis!.code_stats!
    open(
      `/repositories/${REPO_ID}`,
      repositoryDetail({ code_stats: { ...stats, totals: { ...stats.totals, parse_errors: 3 } } }),
    )

    expect(await screen.findByText(/3 files have syntax the parser could not fully read/)).toBeInTheDocument()
  })

  it('groups frameworks by category, with the evidence behind each one', async () => {
    const user = userEvent.setup()
    open(`/repositories/${REPO_ID}`)

    const section = await screen.findByRole('region', { name: 'Frameworks and libraries' })
    expect(within(section).getByRole('heading', { name: 'Backend framework' })).toBeInTheDocument()
    expect(within(section).getByRole('heading', { name: 'Testing' })).toBeInTheDocument()

    await user.click(within(section).getByText('Flask'))
    const dependency = within(section).getByRole('link', { name: 'pyproject.toml:12' })
    expect(dependency).toHaveAttribute('href', `/repositories/${REPO_ID}/files?path=pyproject.toml&line=12`)
    expect(within(section).getByText('flask >=3.0')).toBeInTheDocument()
    expect(within(section).getByRole('link', { name: 'src/flask/app.py:3' })).toBeInTheDocument()
  })

  it('shows file evidence without a line number or detail', async () => {
    const user = userEvent.setup()
    open(`/repositories/${REPO_ID}`)

    const section = await screen.findByRole('region', { name: 'Frameworks and libraries' })
    await user.click(within(section).getByText('pytest'))

    expect(within(section).getByRole('link', { name: 'pytest.ini' })).toHaveAttribute(
      'href',
      `/repositories/${REPO_ID}/files?path=pytest.ini`,
    )
  })

  it('says so when no frameworks were found', async () => {
    open(`/repositories/${REPO_ID}`, repositoryDetail({ technologies: [] }))

    expect(await screen.findByText(/No frameworks or libraries were detected/)).toBeInTheDocument()
  })

  it('lists important files with the reasons, linking to each', async () => {
    open(`/repositories/${REPO_ID}`)

    const section = await screen.findByRole('region', { name: 'Important files' })
    const entry = within(section).getByRole('link', { name: /src\/flask\/app\.py/ })
    expect(entry).toHaveAttribute('href', `/repositories/${REPO_ID}/files?path=${encodeURIComponent('src/flask/app.py')}`)
    expect(entry).toHaveTextContent('Application entry point, Imported by 12 files')
  })

  it('says so when there are no standout files', async () => {
    open(`/repositories/${REPO_ID}`, repositoryDetail({}, { important_files: [] }))

    expect(await screen.findByText('No standout files were found.')).toBeInTheDocument()
  })
})

describe('Dependencies tab', () => {
  const deps = [
    dependency({ name: 'flask', version_spec: '>=3.0', scope: 'runtime', line: 12 }),
    dependency({ name: 'werkzeug', version_spec: null, scope: 'runtime', line: 13 }),
    dependency({ name: 'pytest', version_spec: '>=8', scope: 'dev', line: 30 }),
    dependency({ ecosystem: 'npm', name: 'react', version_spec: '^19', scope: 'runtime', source_file: 'web/package.json', line: 5 }),
  ]
  const url = `/repositories/${REPO_ID}/dependencies`
  const withDeps = (body = deps) => ({ [`GET ${base}/dependencies`]: { body } })

  it('groups dependencies by the file that declares them', async () => {
    open(url, repositoryDetail(), withDeps())

    const python = await screen.findByRole('region', { name: 'pyproject.toml' })
    expect(within(python).getByText('flask')).toBeInTheDocument()
    expect(within(python).getByText('>=3.0')).toBeInTheDocument()
    expect(within(python).getByText('any version')).toBeInTheDocument()
    expect(within(python).getByText('Development')).toBeInTheDocument()
    expect(python).toHaveTextContent('Python, 3 dependencies')
    expect(screen.getByRole('region', { name: 'web/package.json' })).toHaveTextContent('npm, 1 dependency')
  })

  it('links each dependency to its line in the manifest', async () => {
    open(url, repositoryDetail(), withDeps())

    const link = await screen.findByRole('link', { name: 'Line 12 in pyproject.toml' })
    expect(link).toHaveAttribute('href', `/repositories/${REPO_ID}/files?path=pyproject.toml&line=12`)
  })

  it('searches by name', async () => {
    const user = userEvent.setup()
    open(url, repositoryDetail(), withDeps())

    await user.type(await screen.findByRole('searchbox', { name: 'Search dependencies' }), 'WERK')

    const python = screen.getByRole('region', { name: 'pyproject.toml' })
    expect(within(python).getAllByRole('row')).toHaveLength(2) // header row + werkzeug
    expect(within(python).getByText('werkzeug')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'web/package.json' })).not.toBeInTheDocument()
  })

  it('filters by type, offering only the types that exist', async () => {
    const user = userEvent.setup()
    open(url, repositoryDetail(), withDeps())
    const select = await screen.findByRole('combobox', { name: 'Filter by type' })

    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['All types', 'Runtime', 'Development'])
    await user.selectOptions(select, 'dev')

    const main = within(screen.getAllByRole('table')[0])
    expect(main.getByText('pytest')).toBeInTheDocument()
    expect(main.queryByText('flask')).not.toBeInTheDocument()
  })

  it('says so when filters match nothing', async () => {
    const user = userEvent.setup()
    open(url, repositoryDetail(), withDeps())

    await user.type(await screen.findByRole('searchbox', { name: 'Search dependencies' }), 'nothing-like-this')

    expect(screen.getByText('No dependencies match these filters.')).toBeInTheDocument()
  })

  it('explains an empty result', async () => {
    open(url, repositoryDetail(), withDeps([]))

    expect(await screen.findByRole('heading', { name: 'No dependencies found' })).toBeInTheDocument()
  })

  it('reports a failure to load', async () => {
    open(url, repositoryDetail(), { [`GET ${base}/dependencies`]: { status: 500, body: {} } })

    expect(await screen.findByRole('alert')).toHaveTextContent('could not be loaded')
  })
})

describe('Overview tab: technologies used only for development', () => {
  const technologies = [
    {
      name: 'Express',
      category: 'Backend framework',
      dev_only: true,
      evidence: [
        { kind: 'dependency' as const, path: 'package.json', line: 66, detail: 'express ^5.2.1', scope: 'dev' },
        { kind: 'import' as const, path: 'test/browser.ts', line: 3, detail: 'import express' },
      ],
    },
    {
      name: 'React',
      category: 'Frontend framework',
      dev_only: false,
      evidence: [
        { kind: 'dependency' as const, path: 'package.json', line: 10, detail: 'react ^19', scope: 'runtime' },
      ],
    },
  ]

  it('marks them, and only them', async () => {
    open(`/repositories/${REPO_ID}`, repositoryDetail({ technologies }))

    const section = await screen.findByRole('region', { name: 'Frameworks and libraries' })
    const express = within(section).getByText('Express').closest('summary')!
    const react = within(section).getByText('React').closest('summary')!
    expect(express).toHaveTextContent('development only')
    expect(react).not.toHaveTextContent('development only')
  })

  it('says what kind of dependency the evidence is, except for ordinary runtime ones', async () => {
    const user = userEvent.setup()
    open(`/repositories/${REPO_ID}`, repositoryDetail({ technologies }))
    const section = await screen.findByRole('region', { name: 'Frameworks and libraries' })

    await user.click(within(section).getByText('Express'))
    await user.click(within(section).getByText('React'))

    expect(within(section).getByText('express ^5.2.1, development dependency')).toBeInTheDocument()
    expect(within(section).getByText('react ^19')).toBeInTheDocument()
    expect(within(section).getByText('import express')).toBeInTheDocument()
  })

  it('still works for analyses saved before the field existed', async () => {
    const older = [{ name: 'Flask', category: 'Backend framework', evidence: [{ kind: 'file' as const, path: 'a.py', line: null, detail: 'a.py' }] }]
    open(`/repositories/${REPO_ID}`, repositoryDetail({ technologies: older }))

    const section = await screen.findByRole('region', { name: 'Frameworks and libraries' })
    expect(within(section).getByText('Flask').closest('summary')).not.toHaveTextContent('development only')
  })
})
