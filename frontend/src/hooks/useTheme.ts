import { useSyncExternalStore } from 'react'

export type Theme = 'dark' | 'light'

const STORAGE_KEY = 'repinspect-theme'
const THEME_COLOR = { dark: '#0F131A', light: '#F3F5F8' }
const listeners = new Set<() => void>()

/** public/theme-init.js sets the attribute before the first paint, so it is the source of truth. */
const current = (): Theme => (document.documentElement.dataset.theme === 'light' ? 'light' : 'dark')

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function setTheme(theme: Theme) {
  const root = document.documentElement
  // Colours ease over for a moment, then the class goes so normal hover transitions are untouched.
  root.classList.add('theme-changing')
  root.dataset.theme = theme
  window.setTimeout(() => root.classList.remove('theme-changing'), 300)
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLOR[theme])
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // Storage can be blocked; the choice then lasts until the page is closed.
  }
  listeners.forEach((listener) => listener())
}

export function useTheme(): { theme: Theme; setTheme: (theme: Theme) => void } {
  const theme = useSyncExternalStore(subscribe, current, () => 'dark' as Theme)
  return { theme, setTheme }
}
