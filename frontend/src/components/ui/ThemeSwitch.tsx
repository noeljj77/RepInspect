import { Moon, Sun } from 'lucide-react'

import { useTheme } from '../../hooks/useTheme'
import { cn } from '../../lib/cn'

/** A switch between the dark theme (default) and the light theme. */
export default function ThemeSwitch({ label = true, className }: { label?: boolean; className?: string }) {
  const { theme, setTheme } = useTheme()
  const light = theme === 'light'

  return (
    <button
      type="button"
      role="switch"
      aria-checked={light}
      aria-label="Light theme"
      title={light ? 'Switch to the dark theme' : 'Switch to the light theme'}
      onClick={() => setTheme(light ? 'dark' : 'light')}
      className={cn(
        'group inline-flex items-center gap-2.5 rounded-full text-sm text-muted transition-colors hover:text-ink',
        className,
      )}
    >
      {label && <span>Light theme</span>}
      <span
        aria-hidden="true"
        className="relative h-[22px] w-10 shrink-0 rounded-full border border-line bg-raised transition-colors group-hover:border-faint"
      >
        <Sun size={11} className="absolute top-[5px] left-[6px] text-faint" />
        <Moon size={11} className="absolute top-[5px] right-[6px] text-faint" />
        <span
          className={cn(
            'absolute top-[2px] left-[2px] grid size-4 place-items-center rounded-full bg-mark text-mark-ink shadow-sm transition-transform duration-200',
            light && 'translate-x-[18px]',
          )}
        >
          {light ? <Sun size={10} strokeWidth={2.25} /> : <Moon size={10} strokeWidth={2.25} />}
        </span>
      </span>
    </button>
  )
}
