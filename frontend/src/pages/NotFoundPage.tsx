import { Link } from 'react-router'

import { buttonClass } from '../components/ui/button'

export default function NotFoundPage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-start justify-center px-4">
      <p className="font-mono text-sm text-faint">404</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">Page not found</h1>
      <p className="mt-3 text-muted">This address doesn't match any page. Check the link or start from the home page.</p>
      <Link to="/" className={buttonClass('secondary', 'mt-6')}>
        Go to home page
      </Link>
    </main>
  )
}
