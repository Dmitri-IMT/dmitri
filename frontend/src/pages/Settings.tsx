import { useRef, useState, type FormEvent } from 'react'
import { isAxiosError } from 'axios'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { changePassword } from '@/api/passwords'
import type { components } from '@/types/openapi'

type ErrorResponse = components['schemas']['ErrorResponse']

function Settings() {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [currentError, setCurrentError] = useState<string | null>(null)
  const [newError, setNewError] = useState<string | null>(null)
  const [confirmError, setConfirmError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const currentRef = useRef<HTMLInputElement>(null)
  const newRef = useRef<HTMLInputElement>(null)
  const confirmRef = useRef<HTMLInputElement>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setCurrentError(null)
    setNewError(null)
    setConfirmError(null)
    setFormError(null)
    setSuccess(null)
    if (isSubmitting) {
      return
    }
    if (newPassword !== confirmPassword) {
      setConfirmError("Those two passwords don't match.")
      confirmRef.current?.focus()
      return
    }
    setIsSubmitting(true)
    try {
      await changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setSuccess('Password changed.')
    } catch (err) {
      const code = isAxiosError<ErrorResponse>(err)
        ? err.response?.data?.error?.code
        : undefined
      const status = isAxiosError(err) ? err.response?.status : undefined
      if (status === 400 && code === 'wrong_current_password') {
        setCurrentError("That's not your current password.")
        currentRef.current?.focus()
        return
      }
      if (status === 400 && code === 'password_policy_violation') {
        setNewError(
          "That password isn't strong enough. Try a longer one that isn't based on a name or a date.",
        )
        newRef.current?.focus()
        return
      }
      setFormError("Couldn't reach Dmitri. Try again in a moment.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div data-testid="settings-idle" className="flex flex-col gap-12">
      <h1 className="border-b border-rule pb-4 font-title text-title-lg">
        Settings
      </h1>
      <form
        onSubmit={handleSubmit}
        data-testid="settings-form"
        className="flex flex-col gap-4"
      >
        <div className="flex flex-col gap-1">
          <span className="font-title text-title-sm">Change your password</span>
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="settings-current">Current password</Label>
          <Input
            id="settings-current"
            ref={currentRef}
            type="password"
            autoComplete="current-password"
            autoFocus
            aria-invalid={currentError !== null}
            aria-describedby="settings-current-error"
            value={currentPassword}
            onChange={(event) => setCurrentPassword(event.target.value)}
            data-testid="settings-current"
          />
          <p
            id="settings-current-error"
            role="alert"
            data-testid="settings-current-error"
            className="text-sm text-destructive"
          >
            {currentError}
          </p>
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="settings-new">New password</Label>
          <Input
            id="settings-new"
            ref={newRef}
            type="password"
            autoComplete="new-password"
            aria-invalid={newError !== null}
            aria-describedby="settings-new-hint settings-new-error"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            data-testid="settings-new"
          />
          <p
            id="settings-new-hint"
            data-testid="settings-new-hint"
            className="text-sm text-muted-foreground"
          >
            At least 12 characters. Avoid names, dates, and passwords
            you&apos;ve used elsewhere.
          </p>
          <p
            id="settings-new-error"
            role="alert"
            data-testid="settings-new-error"
            className="text-sm text-destructive"
          >
            {newError}
          </p>
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="settings-confirm">Confirm new password</Label>
          <Input
            id="settings-confirm"
            ref={confirmRef}
            type="password"
            autoComplete="new-password"
            aria-invalid={confirmError !== null}
            aria-describedby="settings-confirm-error"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            data-testid="settings-confirm"
          />
          <p
            id="settings-confirm-error"
            role="alert"
            data-testid="settings-confirm-error"
            className="text-sm text-destructive"
          >
            {confirmError}
          </p>
        </div>
        <p
          role="alert"
          data-testid="settings-error"
          className="text-sm text-destructive"
        >
          {formError}
        </p>
        <Button
          type="submit"
          disabled={isSubmitting}
          data-testid="settings-submit"
        >
          {isSubmitting ? 'Changing password…' : 'Change password'}
        </Button>
        <p
          role="status"
          data-testid="settings-success"
          className="text-sm text-muted-foreground"
        >
          {success}
        </p>
      </form>
    </div>
  )
}

export default Settings
