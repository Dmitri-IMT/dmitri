import { useRef, useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import ConfirmByTyping from '@/components/ConfirmByTyping'
import { changePassword } from '@/api/passwords'
import { readApiError } from '@/api/apiError'
import { useSession } from '@/auth/useSession'
import {
  PASSWORD_HINT,
  PASSWORD_MISMATCH_ERROR,
  PASSWORD_POLICY_ERROR,
  SERVICE_ERROR,
} from '@/lib/copy'

const LAST_ADMIN_ERROR =
  "You're the only admin. Make someone else an admin first, then you can leave."
const LEAVE_ERROR = "Couldn't delete your account."

function Settings() {
  const { user, deleteAccount } = useSession()
  const [isLeaveOpen, setIsLeaveOpen] = useState(false)
  const [leaveError, setLeaveError] = useState<string | null>(null)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [currentError, setCurrentError] = useState<string | null>(null)
  const [newError, setNewError] = useState<string | null>(null)
  const [confirmError, setConfirmError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isActivityExpanded, setIsActivityExpanded] = useState(false)
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
      setConfirmError(PASSWORD_MISMATCH_ERROR)
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
      const { status, code } = readApiError(err)
      if (status === 400 && code === 'wrong_current_password') {
        setCurrentError("That's not your current password.")
        currentRef.current?.focus()
        return
      }
      if (status === 400 && code === 'password_policy_violation') {
        setNewError(PASSWORD_POLICY_ERROR)
        newRef.current?.focus()
        return
      }
      setFormError(SERVICE_ERROR)
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleLeave() {
    setLeaveError(null)
    try {
      await deleteAccount()
    } catch (err) {
      const { status, code } = readApiError(err)
      setLeaveError(
        status === 409 && code === 'last_admin'
          ? LAST_ADMIN_ERROR
          : LEAVE_ERROR,
      )
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
            {PASSWORD_HINT}
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
      <section data-testid="settings-activity" className="flex flex-col gap-1">
        <div className="flex items-baseline gap-2">
          <span
            data-testid="settings-activity-label"
            className="font-title text-title-sm"
          >
            Activity
          </span>
          <button
            type="button"
            aria-expanded={isActivityExpanded}
            aria-controls="settings-activity-note"
            data-testid="settings-activity-info"
            className="text-body-md"
            onClick={() => setIsActivityExpanded((expanded) => !expanded)}
          >
            What's recorded?
          </button>
        </div>
        <p
          id="settings-activity-note"
          data-testid="settings-activity-note"
          hidden={!isActivityExpanded}
          className="max-w-prose text-body-md text-muted-foreground"
        >
          Your organization's admins can see when you last used Dmitri and when
          you last signed in. We record only these times — not what you viewed
          or did.
        </p>
      </section>
      {user && (
        <>
          <hr aria-hidden className="border-t border-dashed border-rule" />
          <section data-testid="settings-leave" className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <span className="font-title text-title-sm">
                Leave this organization
              </span>
              <p
                data-testid="settings-leave-body"
                className="max-w-prose text-body-md text-muted-foreground"
              >
                Your account is deleted and you lose access to this
                organization's scans, hosts and findings straight away. This
                can't be undone — an admin would have to invite you again.
              </p>
            </div>
            <Button
              type="button"
              variant="destructive"
              className="self-start"
              onClick={() => setIsLeaveOpen(true)}
              data-testid="settings-leave-trigger"
            >
              Delete my account
            </Button>
          </section>
          <ConfirmByTyping
            open={isLeaveOpen}
            onOpenChange={(open) => {
              setIsLeaveOpen(open)
              if (!open) {
                setLeaveError(null)
              }
            }}
            heading="Delete your account?"
            body="Your account is deleted and you lose access straight away. This can't be undone."
            expectedValue={user.email}
            confirmLabel="Delete my account"
            confirmPendingLabel="Deleting…"
            onConfirm={handleLeave}
            error={leaveError}
          />
        </>
      )}
    </div>
  )
}

export default Settings
