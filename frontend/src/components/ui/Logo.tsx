import { Link } from 'react-router'

export function LogoMark({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect x="2" y="2" width="28" height="28" rx="7" className="fill-surface stroke-line" strokeWidth="2" />
      <rect x="8" y="9" width="12" height="2.5" rx="1.25" className="fill-faint" />
      <rect x="6.5" y="14.25" width="19" height="4" rx="1.5" className="fill-mark" />
      <rect x="8" y="21" width="9" height="2.5" rx="1.25" className="fill-faint" />
    </svg>
  )
}

export function Logo({ to = '/' }: { to?: string }) {
  return (
    <Link to={to} className="inline-flex items-center gap-2.5 text-[17px] font-semibold tracking-tight">
      <LogoMark />
      RepInspect
    </Link>
  )
}
