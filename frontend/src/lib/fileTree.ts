import type { FileEntry } from '../api/repositories'

export interface FolderNode {
  type: 'folder'
  name: string
  path: string
  children: TreeNode[]
  fileCount: number
}

export interface FileNode {
  type: 'file'
  name: string
  path: string
  file: FileEntry
}

export type TreeNode = FolderNode | FileNode

/** Turn the flat list of paths from the API into nested folders, folders first. */
export function buildTree(files: FileEntry[]): FolderNode {
  const root: FolderNode = { type: 'folder', name: '', path: '', children: [], fileCount: 0 }
  const folders = new Map<string, FolderNode>([['', root]])

  for (const file of files) {
    const parts = file.path.split('/')
    let parent = root
    for (let depth = 0; depth < parts.length - 1; depth += 1) {
      const path = parts.slice(0, depth + 1).join('/')
      let folder = folders.get(path)
      if (!folder) {
        folder = { type: 'folder', name: parts[depth], path, children: [], fileCount: 0 }
        folders.set(path, folder)
        parent.children.push(folder)
      }
      folder.fileCount += 1
      parent = folder
    }
    parent.children.push({ type: 'file', name: parts[parts.length - 1], path: file.path, file })
    root.fileCount += 1
  }

  sortTree(root)
  return root
}

function sortTree(folder: FolderNode): void {
  folder.children.sort((a, b) => {
    if (a.type !== b.type) return a.type === 'folder' ? -1 : 1
    return a.name.localeCompare(b.name, 'en', { numeric: true, sensitivity: 'base' })
  })
  for (const child of folder.children) if (child.type === 'folder') sortTree(child)
}

/** "a/b/c.py" -> ["a", "a/b"]: the folders that must be open to show the file. */
export function ancestorFolders(path: string): string[] {
  const parts = path.split('/').slice(0, -1)
  return parts.map((_, index) => parts.slice(0, index + 1).join('/'))
}

/** Files whose path contains every word of the query, best matches (shortest paths) first. */
export function searchFiles(files: FileEntry[], query: string, limit = 100): FileEntry[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  if (words.length === 0) return []
  return files
    .filter((file) => words.every((word) => file.path.toLowerCase().includes(word)))
    .sort((a, b) => a.path.length - b.path.length || a.path.localeCompare(b.path))
    .slice(0, limit)
}
