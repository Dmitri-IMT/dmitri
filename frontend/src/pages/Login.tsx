import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'
import { isAxiosError } from 'axios'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import AuthShell from '@/components/AuthShell'
import { useSession } from '@/auth/useSession'

function Login() {
  const { status, signIn } = useSession()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const [passwordReset] = useState(
    () =>
      (location.state as { passwordReset?: boolean } | null)?.passwordReset ===
      true,
  )

  const successRef = useRef<HTMLParagraphElement>(null)

  useEffect(() => {
    if (passwordReset) {
      successRef.current?.focus()
      void navigate(location.pathname, { replace: true })
    }
  }, [passwordReset, status, location.pathname, navigate])

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
          : "Can't reach the server. Check your connection and try again.",
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell>
      <div className="flex flex-col gap-4">
        {passwordReset && (
          <p
            role="status"
            data-testid="login-success"
            ref={successRef}
            tabIndex={-1}
            className="text-sm text-accent"
          >
            Password set. Sign in with your new password.
          </p>
        )}
        <form
          onSubmit={handleSubmit}
          data-testid="login-form"
          className="flex flex-col gap-4"
        >
          <span className="font-title text-title-sm">Sign in</span>
          <div className="flex flex-col gap-1">
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
          <div className="flex flex-col gap-1">
            <Label htmlFor="login-password">Password</Label>
            <Input
              id="login-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              data-testid="login-password"
            />
          </div>
          <p
            role="alert"
            data-testid="login-error"
            className="text-sm text-destructive"
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
          className="self-center text-sm text-accent underline"
        >
          Forgot password?
        </Link>
      </div>
    </AuthShell>
  )
}

export default Login
