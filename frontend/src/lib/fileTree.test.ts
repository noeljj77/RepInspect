import { fileEntry } from '../test/fixtures'
import { ancestorFolders, buildTree, searchFiles, type FolderNode, type TreeNode } from './fileTree'

const files = [
  'src/app.py',
  'src/api/routes.py',
  'src/api/deps.py',
  'README.md',
  'tests/test_app.py',
  'docs/guide.md',
  'src/z_last.py',
  'src/10-item.py',
  'src/2-item.py',
].map((path) => fileEntry({ path }))

const names = (nodes: TreeNode[]) => nodes.map((n) => n.name)

describe('buildTree', () => {
  const root = buildTree(files)

  it('nests files under their folders', () => {
    const src = root.children.find((n) => n.name === 'src') as FolderNode

    expect(src.type).toBe('folder')
    expect(src.path).toBe('src')
    const api = src.children.find((n) => n.name === 'api') as FolderNode
    expect(api.path).toBe('src/api')
    expect(names(api.children)).toEqual(['deps.py', 'routes.py'])
  })

  it('lists folders before files, each sorted naturally', () => {
    expect(names(root.children)).toEqual(['docs', 'src', 'tests', 'README.md'])
    const src = root.children[1] as FolderNode
    expect(names(src.children)).toEqual(['api', '2-item.py', '10-item.py', 'app.py', 'z_last.py'])
  })

  it('counts the files inside each folder, including nested ones', () => {
    const src = root.children.find((n) => n.name === 'src') as FolderNode

    expect(root.fileCount).toBe(files.length)
    expect(src.fileCount).toBe(6)
  })

  it('gives files their full path and original entry', () => {
    const readme = root.children.find((n) => n.name === 'README.md')

    expect(readme).toMatchObject({ type: 'file', path: 'README.md' })
  })

  it('handles an empty list', () => {
    expect(buildTree([])).toMatchObject({ children: [], fileCount: 0 })
  })
})

describe('ancestorFolders', () => {
  it('lists every folder that contains the file, outermost first', () => {
    expect(ancestorFolders('a/b/c/file.py')).toEqual(['a', 'a/b', 'a/b/c'])
  })

  it('is empty for a file in the root and for no path', () => {
    expect(ancestorFolders('README.md')).toEqual([])
    expect(ancestorFolders('')).toEqual([])
  })
})

describe('searchFiles', () => {
  it('matches case-insensitively on any part of the path', () => {
    expect(searchFiles(files, 'ROUTES').map((f) => f.path)).toEqual(['src/api/routes.py'])
  })

  it('requires every word to match, in any order', () => {
    expect(searchFiles(files, 'py api').map((f) => f.path)).toEqual(['src/api/deps.py', 'src/api/routes.py'])
  })

  it('puts shorter paths first', () => {
    const results = searchFiles(files, 'app').map((f) => f.path)

    expect(results[0]).toBe('src/app.py')
    expect(results).toContain('tests/test_app.py')
  })

  it('returns nothing for a blank query and respects the limit', () => {
    expect(searchFiles(files, '   ')).toEqual([])
    expect(searchFiles(files, 'src', 2)).toHaveLength(2)
  })
})
