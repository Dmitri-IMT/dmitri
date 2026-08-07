import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import AuthShell from '@/components/AuthShell'
import { lookupInvite } from '@/api/auth'
import { useSession } from '@/auth/useSession'
import type { components } from '@/types/openapi'

type ErrorResponse = components['schemas']['ErrorResponse']

function isDeadTokenError(error: unknown): boolean {
  return (
    isAxiosError<ErrorResponse>(error) &&
    error.response?.status === 410 &&
    error.response?.data?.error?.code === 'invalid_invite_token'
  )
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

  const view =
    token === ''
      ? 'dead'
      : status === 'authenticated'
        ? 'signed-in'
        : acceptDead || isDeadTokenError(lookup.error)
          ? 'dead'
          : status !== 'booting' && lookup.isError
            ? 'lookup-error'
            : lookup.data === undefined
              ? 'loading'
              : 'ready'

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
      setConfirmError("Those two passwords don't match.")
      confirmRef.current?.focus()
      return
    }
    setIsSubmitting(true)
    try {
      await acceptInvitation({ token, password })
    } catch (err) {
      const code = isAxiosError<ErrorResponse>(err)
        ? err.response?.data?.error?.code
        : undefined
      const status = isAxiosError(err) ? err.response?.status : undefined
      if (isDeadTokenError(err)) {
        setAcceptDead(true)
        return
      }
      if (status === 400 && code === 'password_policy_violation') {
        setPasswordError(
          "That password isn't strong enough. Try a longer one that isn't based on a name or a date.",
        )
        passwordRef.current?.focus()
        return
      }
      if (status === 400 && code === 'email_already_registered') {
        setAccountError(true)
        accountErrorRef.current?.focus()
        return
      }
      setFormError("Couldn't reach Dmitri. Try again in a moment.")
    } finally {
      setIsSubmitting(false)
    }
  }

  if (view === 'dead') {
    return (
      <AuthShell>
        <div data-testid="invite-dead" className="flex flex-col gap-4">
          <p ref={headingRef} tabIndex={-1} className="font-title text-title-sm">
            This invite has expired.
          </p>
          <p className="text-sm text-muted-foreground">
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
          <p ref={headingRef} tabIndex={-1} className="font-title text-title-sm">
            You&apos;re already signed in.
          </p>
          <p className="text-sm text-muted-foreground">
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
            className="text-sm text-destructive"
          >
            Couldn&apos;t reach Dmitri. Try again in a moment.
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
          <span className="font-title text-title-sm">Create your account</span>
          <p className="text-sm text-muted-foreground">
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
          <span className="font-title text-title-sm">Create your account</span>
          <p className="text-sm text-muted-foreground">
            You&apos;ve been invited to {lookup.data.org_name} with the{' '}
            {lookup.data.role} role. Pick a password and you&apos;re in.
          </p>
          <div className="flex flex-col gap-1">
            <Label htmlFor="invite-password">Password</Label>
            <Input
              id="invite-password"
              ref={passwordRef}
              type="password"
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
              className="text-sm text-muted-foreground"
            >
              At least 12 characters. Avoid names, dates, and passwords
              you&apos;ve used elsewhere.
            </p>
            <p
              id="invite-password-error"
              role="alert"
              data-testid="invite-password-error"
              className="text-sm text-destructive"
            >
              {passwordError}
            </p>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="invite-confirm">Confirm password</Label>
            <Input
              id="invite-confirm"
              ref={confirmRef}
              type="password"
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
              className="text-sm text-destructive"
            >
              {confirmError}
            </p>
          </div>
          <p
            ref={accountErrorRef}
            tabIndex={-1}
            role="alert"
            data-testid="invite-account-error"
            className="text-sm text-destructive"
          >
            {accountError ? (
              <>
                That address already has an account.{' '}
                <Link to="/login" data-testid="invite-sign-in" className="underline">
                  Sign in instead.
                </Link>
              </>
            ) : null}
          </p>
          <p
            role="alert"
            data-testid="invite-error"
            className="text-sm text-destructive"
          >
            {formError}
          </p>
          <Button type="submit" disabled={isSubmitting} data-testid="invite-submit">
            {isSubmitting ? 'Creating your account…' : 'Create account'}
          </Button>
        </form>
      </div>
    </AuthShell>
  )
}

export default AcceptInvite
