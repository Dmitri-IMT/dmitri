import { useEffect, useId, useSyncExternalStore, type ReactNode } from 'react'
import { Popover } from 'radix-ui'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

let activeHint: string | null = null
const listeners = new Set<() => void>()
function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}
function setActive(id: string | null) {
  activeHint = id
  listeners.forEach((listener) => listener())
}

export default function TermHint({
  term,
  label,
  children,
  wide = false,
  ariaLabel,
}: {
  term: string
  label: ReactNode
  children: ReactNode
  wide?: boolean
  ariaLabel?: string
}) {
  const id = useId()
  const active = useSyncExternalStore(
    subscribe,
    () => activeHint,
    () => null,
  )
  const open = active === id
  useEffect(
    () => () => {
      if (activeHint === id) setActive(null)
    },
    [id],
  )
  return (
    <Popover.Root
      open={open}
      onOpenChange={(value) => {
        if (value) setActive(id)
        else if (activeHint === id) setActive(null)
      }}
    >
      <Popover.Trigger asChild>
        <Button
          type="button"
          variant="link"
          aria-label={ariaLabel}
          aria-expanded={open}
          aria-controls={`${id}-hint`}
          data-testid={`term-hint-trigger-${term}`}
          className={cn(
            'inline-flex h-auto p-0 align-baseline text-inherit underline decoration-edge decoration-dotted underline-offset-4 hover:decoration-solid',
            open && 'decoration-solid decoration-ink',
          )}
        >
          {label}
        </Button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          id={`${id}-hint`}
          role="tooltip"
          side="bottom"
          align="start"
          sideOffset={8}
          data-testid={`term-hint-${term}`}
          className={cn(
            'z-50 flex flex-col gap-2 rounded-control bg-ink p-4 text-body-sm text-canvas shadow-md outline-none',
            wide ? 'w-95 p-6' : 'w-80',
          )}
        >
          {children}
          <Popover.Arrow className="fill-ink" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
