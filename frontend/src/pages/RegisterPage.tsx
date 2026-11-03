import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'

import AuthShell from '../components/auth/AuthShell'
import { buttonClass } from '../components/ui/button'
import TextField from '../components/ui/TextField'
import { useRegister } from '../hooks/useAuth'

export default function RegisterPage() {
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const register = useRegister()
  const navigate = useNavigate()

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    register.mutate(
      { display_name: displayName, email, password },
      { onSuccess: () => navigate('/dashboard', { replace: true }) },
    )
  }

  return (
    <AuthShell
      title="Create your account"
      description="Save repositories and track your interview practice."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="text-ink underline underline-offset-4 hover:text-mark-text">
            Log in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <TextField
          label="Name"
          name="name"
          autoComplete="name"
          required
          maxLength={80}
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
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
          autoComplete="new-password"
          required
          minLength={8}
          maxLength={128}
          hint="At least 8 characters."
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {register.isError && (
          <p role="alert" className="text-sm text-danger">
            {register.error.message}
          </p>
        )}

        <button type="submit" disabled={register.isPending} className={buttonClass('primary', 'w-full')}>
          {register.isPending ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthShell>
  )
}
