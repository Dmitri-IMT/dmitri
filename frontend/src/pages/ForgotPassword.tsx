import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import AuthShell from '@/components/AuthShell'
import { forgotPassword } from '@/api/auth'
import { SERVICE_ERROR } from '@/lib/copy'

function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [confirmedFor, setConfirmedFor] = useState<string | null>(null)
  const emailRef = useRef<HTMLInputElement>(null)
  const confirmationRef = useRef<HTMLParagraphElement>(null)

  useEffect(() => {
    if (confirmedFor !== null) {
      confirmationRef.current?.focus()
    }
  }, [confirmedFor])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    if (isSubmitting) {
      return
    }
    setIsSubmitting(true)
    try {
      await forgotPassword({ email })
      setConfirmedFor(email)
    } catch {
      setError(SERVICE_ERROR)
      emailRef.current?.focus()
    } finally {
      setIsSubmitting(false)
    }
  }

  const backLink = (
    <Link
      to="/login"
      data-testid="forgot-back"
      className="cursor-pointer self-center text-body-md text-accent underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      Back to sign in
    </Link>
  )

  if (confirmedFor !== null) {
    return (
      <AuthShell>
        <div
          data-testid="forgot-success"
          className="flex flex-col items-stretch gap-4"
        >
          <p ref={confirmationRef} tabIndex={-1} className="text-title-sm">
            Check your email.
          </p>
          <p className="text-body-md text-muted-foreground">
            If {confirmedFor} has a Dmitri account, a reset link is on its way.
            The link works once and expires shortly.
          </p>
          {backLink}
        </div>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <div data-testid="forgot-idle" className="flex flex-col gap-4">
        <form
          onSubmit={handleSubmit}
          data-testid="forgot-form"
          className="flex flex-col gap-4"
        >
          <span className="text-title-sm">Reset your password</span>
          <p className="text-body-md text-muted-foreground">
            Enter your email and we&apos;ll send you a link to set a new
            password.
          </p>
          <div className="flex flex-col gap-2">
            <Label htmlFor="forgot-email">Email</Label>
            <Input
              id="forgot-email"
              ref={emailRef}
              type="email"
              autoComplete="email"
              autoFocus
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              data-testid="forgot-email"
            />
          </div>
          <p
            role="alert"
            data-testid="forgot-error"
            className="text-body-md text-ink"
          >
            {error}
          </p>
          <Button
            type="submit"
            disabled={isSubmitting}
            data-testid="forgot-submit"
          >
            {isSubmitting ? 'Sending…' : 'Send reset link'}
          </Button>
        </form>
        {backLink}
      </div>
    </AuthShell>
  )
}

export default ForgotPassword
