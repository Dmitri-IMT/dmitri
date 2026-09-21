import { useRef, useState, type ReactNode } from 'react'
import { Collapsible } from 'radix-ui'
import { Card, CardContent, CardHeader } from '@/components/ui/card'

function ScanDetailSection({
  title,
  children,
  defaultOpen = false,
  openWhen = false,
  triggerAriaLabel,
}: {
  title: ReactNode
  children: ReactNode
  defaultOpen?: boolean
  openWhen?: boolean
  triggerAriaLabel?: string
}) {
  const [open, setOpen] = useState(defaultOpen || openWhen)
  const wasOpenWhen = useRef(openWhen)
  if (openWhen && !wasOpenWhen.current && !open) {
    setOpen(true)
  }
  wasOpenWhen.current = openWhen
  return (
    <Collapsible.Root open={open} onOpenChange={setOpen}>
      <Card>
        <CardHeader className="p-0">
          <Collapsible.Trigger
            className="flex w-full cursor-pointer items-center justify-between px-6 py-4 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
            aria-label={triggerAriaLabel}
          >
            <h2 className="text-title-sm">{title}</h2>
            <span
              aria-hidden="true"
              className="text-title-sm leading-none text-muted-foreground transition-transform data-[state=open]:rotate-90"
            >
              ›
            </span>
          </Collapsible.Trigger>
        </CardHeader>
        <Collapsible.Content forceMount asChild>
          <CardContent className="data-[state=closed]:hidden">
            {children}
          </CardContent>
        </Collapsible.Content>
      </Card>
    </Collapsible.Root>
  )
}

export default ScanDetailSection
