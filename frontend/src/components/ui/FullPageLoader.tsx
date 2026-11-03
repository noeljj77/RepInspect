import { LogoMark } from './Logo'

/** A whole-page wait, such as checking the session on first load. */
export default function FullPageLoader({ children }: { children: string }) {
  return (
    <div role="status" className="grid min-h-dvh place-items-center px-4">
      <div className="flex flex-col items-center gap-4 text-sm text-muted">
        <span className="animate-pulse">
          <LogoMark size={40} />
        </span>
        <span
          aria-hidden="true"
          className="bar-indeterminate relative block h-1 w-36 overflow-hidden rounded-full bg-raised text-mark"
        >
          <span />
        </span>
        {children}
      </div>
    </div>
  )
}
