import { useRef, useState } from 'react'
import { Dialog } from 'radix-ui'
import DialogShell from '@/components/DialogShell'
import { Button } from '@/components/ui/button'

type ConfirmDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  confirmLabel: string
  pendingLabel: string
  onConfirm: () => Promise<void>
  error?: string | null
  testId: string
}

function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  pendingLabel,
  onConfirm,
  error = null,
  testId,
}: ConfirmDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const confirmRef = useRef<HTMLButtonElement>(null)

  async function handleConfirm() {
    if (isSubmitting) return
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
      testId={`${testId}-dialog`}
      locked={isSubmitting}
      initialFocusRef={confirmRef}
    >
      <Dialog.Title className="text-title-sm">{title}</Dialog.Title>
      <Dialog.Description className="max-w-prose text-body-md text-muted-foreground">
        {description}
      </Dialog.Description>
      <p
        role="alert"
        data-testid={`${testId}-error`}
        className="text-body-sm text-ink"
      >
        {error}
      </p>
      <div className="flex justify-end gap-2">
        {!isSubmitting && (
          <Dialog.Close asChild>
            <Button
              type="button"
              variant="outline"
              data-testid={`${testId}-cancel`}
            >
              Cancel
            </Button>
          </Dialog.Close>
        )}
        <Button
          ref={confirmRef}
          type="button"
          onClick={() => void handleConfirm()}
          disabled={isSubmitting}
          data-testid={`${testId}-confirm`}
        >
          {isSubmitting ? pendingLabel : confirmLabel}
        </Button>
      </div>
    </DialogShell>
  )
}

export default ConfirmDialog
