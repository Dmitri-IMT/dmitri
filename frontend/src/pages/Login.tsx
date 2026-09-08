import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { isAxiosError } from 'axios'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PasswordInput } from '@/components/ui/password-input'
import AuthShell from '@/components/AuthShell'
import { useSession } from '@/auth/useSession'
import { SERVICE_ERROR } from '@/lib/copy'

function Login() {
  const { status, signIn } = useSession()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const [arrival] = useState(() => {
    const state = location.state as {
      passwordReset?: boolean
      accountDeleted?: boolean
    } | null
    if (state?.accountDeleted === true) return 'accountDeleted' as const
    if (state?.passwordReset === true) return 'passwordReset' as const
    return null
  })

  const successRef = useRef<HTMLParagraphElement>(null)

  useEffect(() => {
    if (arrival !== null) {
      successRef.current?.focus()
      void navigate(location.pathname, { replace: true })
    }
  }, [arrival, status, location.pathname, navigate])

  if (status === 'authenticated') {
    return <Navigate to="/" replace />
  }

  if (status === 'booting') {
    return null
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isSubmitting) {
      return
    }
    setError(null)
    setIsSubmitting(true)
    try {
      await signIn({ email, password })
    } catch (err) {
      setError(
        isAxiosError(err) && err.response?.status === 401
          ? "That email and password don't match."
          : SERVICE_ERROR,
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell>
      <div className="flex flex-col gap-4">
        {arrival !== null && (
          <p
            role="status"
            data-testid="login-success"
            ref={successRef}
            tabIndex={-1}
            className="text-body-md text-ink"
          >
            {arrival === 'accountDeleted'
              ? 'Your account has been deleted.'
              : 'Password set. Sign in with your new password.'}
          </p>
        )}
        <form
          onSubmit={handleSubmit}
          data-testid="login-form"
          className="flex flex-col gap-4"
        >
          <span className="text-title-sm">Sign in</span>
          <div className="flex flex-col gap-2">
            <Label htmlFor="login-email">Email</Label>
            <Input
              id="login-email"
              type="email"
              autoComplete="email"
              autoFocus
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              data-testid="login-email"
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="login-password">Password</Label>
            <PasswordInput
              id="login-password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              data-testid="login-password"
            />
          </div>
          <p
            role="alert"
            data-testid="login-error"
            className="text-body-md text-ink"
          >
            {error}
          </p>
          <Button
            type="submit"
            disabled={isSubmitting}
            data-testid="login-submit"
          >
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
        <Link
          to="/forgot-password"
          className="cursor-pointer self-center text-body-md text-accent underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          Forgot password?
        </Link>
      </div>
    </AuthShell>
  )
}

export default Login
