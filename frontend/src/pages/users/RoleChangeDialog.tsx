import { useRef, useState } from 'react'
import { Dialog } from 'radix-ui'
import DialogShell from '@/components/DialogShell'
import { Button } from '@/components/ui/button'
import { ROLE_NOUN, type Role } from '@/lib/directory'

type RoleChangeDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  email: string
  nextRole: Role
  onConfirm: () => Promise<void>
  error?: string | null
}

const BODY = {
  admin: "They'll be able to run scans and invite people.",
  viewer: "They'll only be able to see scans, hosts and findings.",
} as const

function RoleChangeDialog({
  open,
  onOpenChange,
  email,
  nextRole,
  onConfirm,
  error = null,
}: RoleChangeDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const confirmRef = useRef<HTMLButtonElement>(null)

  async function handleConfirm() {
    if (isSubmitting) {
      return
    }
    setIsSubmitting(true)
    try {
      await onConfirm()
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <DialogShell
      open={open}
      onOpenChange={onOpenChange}
      testId="role-dialog"
      locked={isSubmitting}
      initialFocusRef={confirmRef}
    >
      <Dialog.Title className="font-title text-title-sm">
        Make {email} {ROLE_NOUN[nextRole]}?
      </Dialog.Title>
      <Dialog.Description className="max-w-prose text-body-md text-muted-foreground">
        {BODY[nextRole]}
      </Dialog.Description>
      <p
        role="alert"
        data-testid="role-error"
        className="text-body-sm text-destructive"
      >
        {error}
      </p>
      <div className="flex justify-end gap-2">
        {!isSubmitting && (
          <Dialog.Close asChild>
            <Button type="button" variant="outline">
              Cancel
            </Button>
          </Dialog.Close>
        )}
        <Button
          ref={confirmRef}
          type="button"
          onClick={handleConfirm}
          disabled={isSubmitting}
          data-testid="role-confirm"
        >
          {isSubmitting ? 'Changing…' : 'Change role'}
        </Button>
      </div>
    </DialogShell>
  )
}

export default RoleChangeDialog
