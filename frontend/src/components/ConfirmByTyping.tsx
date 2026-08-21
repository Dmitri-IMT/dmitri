import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { Dialog } from 'radix-ui'
import DialogShell from '@/components/DialogShell'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

type ConfirmByTypingProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  heading: string
  body: string
  expectedValue: string
  confirmLabel: string
  confirmPendingLabel: string
  onConfirm: () => Promise<void>
  error?: string | null
}

function matchesExpected(typed: string, expected: string): boolean {
  return typed.trim().toLowerCase() === expected.trim().toLowerCase()
}

function ConfirmByTyping({
  open,
  onOpenChange,
  heading,
  body,
  expectedValue,
  confirmLabel,
  confirmPendingLabel,
  onConfirm,
  error = null,
}: ConfirmByTypingProps) {
  const [typed, setTyped] = useState('')
  const [wasOpen, setWasOpen] = useState(open)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const errorRef = useRef<HTMLParagraphElement>(null)
  const inputId = useId()
  const promptId = useId()

  // Radix unmounts `Dialog.Content` on close, but this component stays mounted alongside
  // its caller, so `typed` outlives the dialog. Clearing it on the way open is
  // load-bearing: without it a cancelled attempt reopens with the address already filled
  // in and the destructive action already live, and the typing gate holds only once.
  // React's reset-on-prop-change pattern, not an effect — the value must be right on the
  // first render of the reopened dialog, not one paint later.
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) {
      setTyped('')
    }
  }

  useEffect(() => {
    if (error) {
      errorRef.current?.focus()
    }
  }, [error])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isSubmitting || !matchesExpected(typed, expectedValue)) {
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
      testId="confirm-by-typing-dialog"
      locked={isSubmitting}
    >
      <Dialog.Title className="font-title text-title-sm">
        {heading}
      </Dialog.Title>
      <Dialog.Description className="max-w-prose text-body-md text-muted-foreground">
        {body}
      </Dialog.Description>
      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <label
            id={promptId}
            htmlFor={inputId}
            data-testid="confirm-by-typing-prompt"
            className="text-body-md"
          >
            Type {expectedValue} to confirm.
          </label>
          <Input
            id={inputId}
            type="text"
            autoComplete="off"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            data-testid="confirm-by-typing-input"
          />
          <p
            ref={errorRef}
            role="alert"
            tabIndex={-1}
            data-testid="confirm-by-typing-error"
            className="text-body-sm text-destructive"
          >
            {error}
          </p>
        </div>
        <div className="flex justify-end gap-2">
          {!isSubmitting && (
            <Dialog.Close asChild>
              <Button
                type="button"
                variant="outline"
                data-testid="confirm-by-typing-cancel"
              >
                Cancel
              </Button>
            </Dialog.Close>
          )}
          <Button
            type="submit"
            variant="destructive"
            aria-describedby={promptId}
            disabled={!matchesExpected(typed, expectedValue) || isSubmitting}
            data-testid="confirm-by-typing-submit"
          >
            {isSubmitting ? confirmPendingLabel : confirmLabel}
          </Button>
        </div>
      </form>
    </DialogShell>
  )
}

export default ConfirmByTyping
