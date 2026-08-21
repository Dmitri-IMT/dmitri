import { useRef, useState } from 'react'
import { Dialog } from 'radix-ui'
import DialogShell from '@/components/DialogShell'
import { Button } from '@/components/ui/button'

type RevokeDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  email: string
  onConfirm: () => Promise<void>
  error?: string | null
}

function RevokeDialog({
  open,
  onOpenChange,
  email,
  onConfirm,
  error = null,
}: RevokeDialogProps) {
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
      testId="revoke-dialog"
      locked={isSubmitting}
      initialFocusRef={confirmRef}
    >
      <Dialog.Title className="font-title text-title-sm">
        Revoke the invite to {email}?
      </Dialog.Title>
      <Dialog.Description className="max-w-prose text-body-md text-muted-foreground">
        Their link stops working immediately. You can invite them again later.
      </Dialog.Description>
      <p
        role="alert"
        data-testid="revoke-error"
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
          data-testid="revoke-confirm"
        >
          {isSubmitting ? 'Revoking…' : 'Revoke'}
        </Button>
      </div>
    </DialogShell>
  )
}

export default RevokeDialog
