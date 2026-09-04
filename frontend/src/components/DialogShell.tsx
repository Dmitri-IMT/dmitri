import { useLayoutEffect, useRef, type ReactNode, type RefObject } from 'react'
import { Dialog, DialogContent } from '@/components/ui/dialog'

// `sm:` because the primitive's own cap is `sm:max-w-md`; an unprefixed width would lose
// to it above 640px and every dialog would render at the same size.
const WIDTH = { sm: 'sm:max-w-sm', md: 'sm:max-w-md' } as const

type DialogShellProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  testId: string
  // Panel width. `sm` is for dialogs whose content is a short form and reads better
  // narrow and tall; `md` is the default for prose-led confirmations.
  size?: 'sm' | 'md'
  // Blocks every dismissal — overlay click, Escape, Cancel — while an action is in flight.
  locked?: boolean
  // Focused on open instead of the first tabbable element.
  initialFocusRef?: RefObject<HTMLElement | null>
  children: ReactNode
}

// Every caller opens its dialog from state rather than a `Dialog.Trigger`, so Radix has
// no trigger to hand focus back to on close and drops it on `<body>`. Capturing the
// opener ourselves and restoring it by hand keeps the keyboard where the user left it.
function DialogShell({
  open,
  onOpenChange,
  testId,
  size = 'md',
  locked = false,
  initialFocusRef,
  children,
}: DialogShellProps) {
  const openerRef = useRef<Element | null>(null)

  useLayoutEffect(() => {
    if (open) {
      openerRef.current = document.activeElement
    }
  }, [open])

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!locked) {
          onOpenChange(next)
        }
      }}
    >
      <DialogContent
        data-testid={testId}
        showCloseButton={false}
        onOpenAutoFocus={
          initialFocusRef
            ? (event) => {
                event.preventDefault()
                initialFocusRef.current?.focus()
              }
            : undefined
        }
        onCloseAutoFocus={(event) => {
          event.preventDefault()
          const opener = openerRef.current
          if (opener instanceof HTMLElement && opener.isConnected) {
            opener.focus()
          }
        }}
        className={WIDTH[size]}
      >
        {children}
      </DialogContent>
    </Dialog>
  )
}

export default DialogShell
