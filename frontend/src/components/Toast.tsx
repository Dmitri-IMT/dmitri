import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { Toast } from 'radix-ui'
import { ToastContext } from '@/hooks/useToast'

type RaisedToast = {
  id: number
  message: string
}

function ToastProvider({
  children,
  duration = 5000,
}: {
  children: ReactNode
  duration?: number
}) {
  const [raised, setRaised] = useState<RaisedToast | null>(null)

  const show = useCallback((message: string) => {
    setRaised((current) => ({ id: (current?.id ?? 0) + 1, message }))
  }, [])

  const value = useMemo(() => ({ show }), [show])

  return (
    <ToastContext.Provider value={value}>
      <Toast.Provider duration={duration}>
        {children}
        {raised && (
          <Toast.Root
            key={raised.id}
            data-testid="toast"
            onOpenChange={(open) => {
              if (!open) {
                setRaised(null)
              }
            }}
            className="flex items-center gap-4 border border-input bg-card p-4"
          >
            <Toast.Description className="text-body-md">
              {raised.message}
            </Toast.Description>
            <Toast.Close className="cursor-pointer text-body-sm text-muted-foreground underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none">
              Dismiss
            </Toast.Close>
          </Toast.Root>
        )}
        {createPortal(
          <Toast.Viewport className="fixed right-4 bottom-4 flex w-full max-w-sm flex-col" />,
          document.body,
        )}
      </Toast.Provider>
    </ToastContext.Provider>
  )
}

export default ToastProvider
