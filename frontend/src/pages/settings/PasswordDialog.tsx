import { useRef, useState, type FormEvent } from 'react'
import { Dialog } from 'radix-ui'
import { readApiError } from '@/api/apiError'
import { changePassword } from '@/api/passwords'
import DialogShell from '@/components/DialogShell'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  PASSWORD_HINT,
  PASSWORD_MISMATCH_ERROR,
  PASSWORD_POLICY_ERROR,
  SERVICE_ERROR,
} from '@/lib/copy'

type PasswordDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

function PasswordDialog({
  open,
  onOpenChange,
  onSuccess,
}: PasswordDialogProps) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [currentError, setCurrentError] = useState<string | null>(null)
  const [newError, setNewError] = useState<string | null>(null)
  const [confirmError, setConfirmError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
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
      onSuccess()
      onOpenChange(false)
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

  return (
    <DialogShell
      open={open}
      onOpenChange={onOpenChange}
      testId="settings-password-dialog"
      size="sm"
      locked={isSubmitting}
      initialFocusRef={currentRef}
    >
      <form
        onSubmit={handleSubmit}
        data-testid="settings-form"
        className="flex flex-col gap-4"
      >
        <Dialog.Title className="text-title-sm">
          Change your password
        </Dialog.Title>
        <div className="flex flex-col gap-1">
          <Label htmlFor="settings-current">Current password</Label>
          <Input
            id="settings-current"
            ref={currentRef}
            type="password"
            autoComplete="current-password"
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
            className="text-body-md text-ink"
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
            className="text-body-md text-muted-foreground"
          >
            {PASSWORD_HINT}
          </p>
          <p
            id="settings-new-error"
            role="alert"
            data-testid="settings-new-error"
            className="text-body-md text-ink"
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
            className="text-body-md text-ink"
          >
            {confirmError}
          </p>
        </div>
        <p
          role="alert"
          data-testid="settings-error"
          className="text-body-md text-ink"
        >
          {formError}
        </p>
        <div className="flex justify-end gap-2 pt-2">
          {!isSubmitting && (
            <Dialog.Close asChild>
              <Button
                type="button"
                variant="outline"
                data-testid="settings-password-cancel"
              >
                Cancel
              </Button>
            </Dialog.Close>
          )}
          <Button
            type="submit"
            disabled={isSubmitting}
            data-testid="settings-submit"
          >
            {isSubmitting ? 'Changing password…' : 'Change password'}
          </Button>
        </div>
      </form>
    </DialogShell>
  )
}

export default PasswordDialog
