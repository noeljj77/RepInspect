import { Link } from 'react-router'

import { buttonClass } from '../ui/button'
import { Logo } from '../ui/Logo'

export default function PublicHeader() {
  return (
    <header className="border-b border-line/70">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Logo />
        <nav className="flex items-center gap-1 sm:gap-2">
          <a href="#how-it-works" className={buttonClass('ghost', 'max-sm:hidden')}>
            How it works
          </a>
          <Link to="/dashboard" className={buttonClass('primary')}>
            Get started
          </Link>
        </nav>
      </div>
    </header>
  )
}
