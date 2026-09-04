import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import AuthShell from '@/components/AuthShell'
import { resetPassword } from '@/api/auth'
import { readApiError } from '@/api/apiError'
import {
  PASSWORD_HINT,
  PASSWORD_MISMATCH_ERROR,
  PASSWORD_POLICY_ERROR,
  SERVICE_ERROR,
} from '@/lib/copy'

function ResetPassword() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''
  const navigate = useNavigate()
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [confirmError, setConfirmError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isDead, setIsDead] = useState(token === '')
  const passwordRef = useRef<HTMLInputElement>(null)
  const confirmRef = useRef<HTMLInputElement>(null)
  const deadRef = useRef<HTMLParagraphElement>(null)

  useEffect(() => {
    if (isDead) {
      deadRef.current?.focus()
    }
  }, [isDead])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPasswordError(null)
    setConfirmError(null)
    setFormError(null)
    if (isSubmitting) {
      return
    }
    if (newPassword !== confirmPassword) {
      setConfirmError(PASSWORD_MISMATCH_ERROR)
      confirmRef.current?.focus()
      return
    }
    setIsSubmitting(true)
    try {
      await resetPassword({ token, new_password: newPassword })
      void navigate('/login', { replace: true, state: { passwordReset: true } })
    } catch (err) {
      const { status, code } = readApiError(err)
      if (status === 410 && code === 'invalid_reset_token') {
        setIsDead(true)
        return
      }
      if (status === 400 && code === 'password_policy_violation') {
        setPasswordError(PASSWORD_POLICY_ERROR)
        passwordRef.current?.focus()
        return
      }
      setFormError(SERVICE_ERROR)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (isDead) {
    return (
      <AuthShell>
        <div data-testid="reset-dead" className="flex flex-col gap-4">
          <p ref={deadRef} tabIndex={-1} className="text-title-sm">
            This link has expired.
          </p>
          <p className="text-body-md text-muted-foreground">
            Reset links work once and don&apos;t last long.
          </p>
          <Link
            to="/forgot-password"
            data-testid="reset-request"
            className="cursor-pointer self-center text-body-md text-accent underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
          >
            Request a new link
          </Link>
        </div>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <div data-testid="reset-idle" className="flex flex-col gap-4">
        <form
          onSubmit={handleSubmit}
          data-testid="reset-form"
          className="flex flex-col gap-4"
        >
          <span className="text-title-sm">Set a new password</span>
          <div className="flex flex-col gap-2">
            <Label htmlFor="reset-password">New password</Label>
            <Input
              id="reset-password"
              ref={passwordRef}
              type="password"
              autoComplete="new-password"
              autoFocus
              aria-invalid={passwordError !== null}
              aria-describedby="reset-password-hint reset-password-error"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              data-testid="reset-password"
            />
            <p
              id="reset-password-hint"
              data-testid="reset-password-hint"
              className="text-body-md text-muted-foreground"
            >
              {PASSWORD_HINT}
            </p>
            <p
              id="reset-password-error"
              role="alert"
              data-testid="reset-password-error"
              className="text-body-md text-ink"
            >
              {passwordError}
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="reset-confirm">Confirm new password</Label>
            <Input
              id="reset-confirm"
              ref={confirmRef}
              type="password"
              autoComplete="new-password"
              aria-invalid={confirmError !== null}
              aria-describedby="reset-confirm-error"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              data-testid="reset-confirm"
            />
            <p
              id="reset-confirm-error"
              role="alert"
              data-testid="reset-confirm-error"
              className="text-body-md text-ink"
            >
              {confirmError}
            </p>
          </div>
          <p
            role="alert"
            data-testid="reset-error"
            className="text-body-md text-ink"
          >
            {formError}
          </p>
          <Button
            type="submit"
            disabled={isSubmitting}
            data-testid="reset-submit"
          >
            {isSubmitting ? 'Setting your password…' : 'Set password'}
          </Button>
        </form>
      </div>
    </AuthShell>
  )
}

export default ResetPassword
