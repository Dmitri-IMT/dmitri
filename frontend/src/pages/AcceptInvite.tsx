import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { PasswordInput } from '@/components/ui/password-input'
import AuthShell from '@/components/AuthShell'
import { lookupInvite } from '@/api/auth'
import { readApiError } from '@/api/apiError'
import { useSession } from '@/auth/useSession'
import {
  PASSWORD_HINT,
  PASSWORD_MISMATCH_ERROR,
  PASSWORD_POLICY_ERROR,
  SERVICE_ERROR,
} from '@/lib/copy'

type InviteView = 'dead' | 'signed-in' | 'lookup-error' | 'loading' | 'ready'

function isDeadTokenError(error: unknown): boolean {
  const { status, code } = readApiError(error)
  return status === 410 && code === 'invalid_invite_token'
}

function AcceptInvite() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''
  const { status, signOut, acceptInvitation } = useSession()
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [confirmError, setConfirmError] = useState<string | null>(null)
  const [accountError, setAccountError] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [acceptDead, setAcceptDead] = useState(false)
  const passwordRef = useRef<HTMLInputElement>(null)
  const confirmRef = useRef<HTMLInputElement>(null)
  const accountErrorRef = useRef<HTMLParagraphElement>(null)
  const headingRef = useRef<HTMLParagraphElement>(null)

  const lookup = useQuery({
    queryKey: ['invite', 'lookup', token],
    queryFn: () => lookupInvite({ token }),
    enabled: token !== '' && status === 'anonymous',
    retry: false,
  })

  function resolveView(): InviteView {
    if (token === '') return 'dead'
    if (status === 'authenticated') return 'signed-in'
    if (acceptDead || isDeadTokenError(lookup.error)) return 'dead'
    if (status !== 'booting' && lookup.isError) return 'lookup-error'
    if (lookup.data === undefined) return 'loading'
    return 'ready'
  }

  const view = resolveView()

  useEffect(() => {
    if (view === 'dead' || view === 'signed-in' || view === 'lookup-error') {
      headingRef.current?.focus()
    }
  }, [view])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPasswordError(null)
    setConfirmError(null)
    setAccountError(false)
    setFormError(null)
    if (isSubmitting) {
      return
    }
    if (password !== confirmPassword) {
      setConfirmError(PASSWORD_MISMATCH_ERROR)
      confirmRef.current?.focus()
      return
    }
    setIsSubmitting(true)
    try {
      await acceptInvitation({ token, password })
    } catch (err) {
      // `httpStatus`, not `status` — the latter is the session status from useSession above.
      const { status: httpStatus, code } = readApiError(err)
      if (isDeadTokenError(err)) {
        setAcceptDead(true)
        return
      }
      if (httpStatus === 400 && code === 'password_policy_violation') {
        setPasswordError(PASSWORD_POLICY_ERROR)
        passwordRef.current?.focus()
        return
      }
      if (httpStatus === 400 && code === 'email_already_registered') {
        setAccountError(true)
        accountErrorRef.current?.focus()
        return
      }
      setFormError(SERVICE_ERROR)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (view === 'dead') {
    return (
      <AuthShell>
        <div data-testid="invite-dead" className="flex flex-col gap-4">
          <p ref={headingRef} tabIndex={-1} className="text-title-sm">
            This invite has expired.
          </p>
          <p className="text-body-md text-muted-foreground">
            Invite links can only be used once, and they don&apos;t last long.
            Ask your admin to send you a new one.
          </p>
        </div>
      </AuthShell>
    )
  }

  if (view === 'signed-in') {
    return (
      <AuthShell>
        <div data-testid="invite-signed-in" className="flex flex-col gap-4">
          <p ref={headingRef} tabIndex={-1} className="text-title-sm">
            You&apos;re already signed in.
          </p>
          <p className="text-body-md text-muted-foreground">
            Sign out first to accept this invite.
          </p>
          <Button
            type="button"
            onClick={() => void signOut()}
            data-testid="invite-sign-out"
          >
            Sign out
          </Button>
        </div>
      </AuthShell>
    )
  }

  if (view === 'lookup-error') {
    return (
      <AuthShell>
        <div className="flex flex-col gap-4">
          <p
            ref={headingRef}
            tabIndex={-1}
            role="alert"
            data-testid="invite-error"
            className="text-body-md text-ink"
          >
            {SERVICE_ERROR}
          </p>
          <Button
            type="button"
            onClick={() => void lookup.refetch()}
            data-testid="invite-retry"
          >
            Retry
          </Button>
        </div>
      </AuthShell>
    )
  }

  if (lookup.data === undefined) {
    return (
      <AuthShell>
        <div
          data-testid="invite-loading"
          aria-busy="true"
          className="flex flex-col gap-4"
        >
          <span className="text-title-sm">Create your account</span>
          <p className="text-body-md text-muted-foreground">
            Checking your invite…
          </p>
        </div>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <div data-testid="invite-ready" className="flex flex-col gap-4">
        <form
          onSubmit={handleSubmit}
          data-testid="invite-form"
          className="flex flex-col gap-4"
        >
          <span className="text-title-sm">Create your account</span>
          <p className="text-body-md text-muted-foreground">
            You&apos;ve been invited to {lookup.data.org_name} with the{' '}
            {lookup.data.role} role. Pick a password and you&apos;re in.
          </p>
          <div className="flex flex-col gap-2">
            <Label htmlFor="invite-password">Password</Label>
            <PasswordInput
              id="invite-password"
              ref={passwordRef}
              autoComplete="new-password"
              autoFocus
              aria-invalid={passwordError !== null}
              aria-describedby="invite-password-hint invite-password-error"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              data-testid="invite-password"
            />
            <p
              id="invite-password-hint"
              data-testid="invite-password-hint"
              className="text-body-md text-muted-foreground"
            >
              {PASSWORD_HINT}
            </p>
            <p
              id="invite-password-error"
              role="alert"
              data-testid="invite-password-error"
              className="text-body-md text-ink"
            >
              {passwordError}
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="invite-confirm">Confirm password</Label>
            <PasswordInput
              id="invite-confirm"
              ref={confirmRef}
              autoComplete="new-password"
              aria-invalid={confirmError !== null}
              aria-describedby="invite-confirm-error"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              data-testid="invite-confirm"
            />
            <p
              id="invite-confirm-error"
              role="alert"
              data-testid="invite-confirm-error"
              className="text-body-md text-ink"
            >
              {confirmError}
            </p>
          </div>
          <p
            ref={accountErrorRef}
            tabIndex={-1}
            role="alert"
            data-testid="invite-account-error"
            className="text-body-md text-ink"
          >
            {accountError ? (
              <>
                That address already has an account.{' '}
                <Link
                  to="/login"
                  data-testid="invite-sign-in"
                  className="cursor-pointer underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  Sign in instead.
                </Link>
              </>
            ) : null}
          </p>
          <p
            role="alert"
            data-testid="invite-error"
            className="text-body-md text-ink"
          >
            {formError}
          </p>
          <Button
            type="submit"
            disabled={isSubmitting}
            data-testid="invite-submit"
          >
            {isSubmitting ? 'Creating your account…' : 'Create account'}
          </Button>
        </form>
      </div>
    </AuthShell>
  )
}

export default AcceptInvite
