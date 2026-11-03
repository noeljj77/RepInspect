import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'

import AuthShell from '../components/auth/AuthShell'
import { buttonClass } from '../components/ui/button'
import TextField from '../components/ui/TextField'
import { useLogin } from '../hooks/useAuth'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const login = useLogin()
  const navigate = useNavigate()
  const location = useLocation()

  // RequireAuth stores the page the person was trying to reach.
  const destination = (location.state as { from?: string } | null)?.from ?? '/dashboard'

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    login.mutate({ email, password }, { onSuccess: () => navigate(destination, { replace: true }) })
  }

  return (
    <AuthShell
      title="Log in"
      description="Pick up where you left off."
      footer={
        <>
          New to RepInspect?{' '}
          <Link to="/register" className="text-ink underline underline-offset-4 hover:text-mark-text">
            Create an account
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <TextField
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <TextField
          label="Password"
          type="password"
          name="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {login.isError && (
          <p role="alert" className="text-sm text-danger">
            {login.error.message}
          </p>
        )}

        <button type="submit" disabled={login.isPending} className={buttonClass('primary', 'w-full')}>
          {login.isPending ? 'Logging in…' : 'Log in'}
        </button>
      </form>
    </AuthShell>
  )
}
