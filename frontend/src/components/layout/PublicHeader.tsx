import { Link } from 'react-router'

import { useCurrentUser } from '../../hooks/useAuth'
import { buttonClass } from '../ui/button'
import { Logo } from '../ui/Logo'

export default function PublicHeader() {
  const { data: user } = useCurrentUser()

  return (
    <header className="border-b border-line/70">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Logo />
        <nav className="flex items-center gap-1 sm:gap-2">
          <a href="#how-it-works" className={buttonClass('ghost', 'max-sm:hidden')}>
            How it works
          </a>
          {user ? (
            <Link to="/dashboard" className={buttonClass('primary')}>
              Open dashboard
            </Link>
          ) : (
            <>
              <Link to="/login" className={buttonClass('ghost')}>
                Log in
              </Link>
              <Link to="/register" className={buttonClass('primary')}>
                Sign up
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  )
}
