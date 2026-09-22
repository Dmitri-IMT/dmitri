import { useState, type ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { Collapsible } from 'radix-ui'
import { Card, CardContent, CardHeader } from '@/components/ui/card'

function ScanDetailSection({
  title,
  children,
  openToken,
  triggerAriaLabel,
}: {
  title: ReactNode
  children: ReactNode
  /** Opens the section each time it changes to a new value (e.g. a deep-linked finding id). Never forces it closed. */
  openToken?: string
  triggerAriaLabel?: string
}) {
  const [open, setOpen] = useState(openToken != null)
  const [lastOpenToken, setLastOpenToken] = useState(openToken)

  if (openToken !== lastOpenToken) {
    setLastOpenToken(openToken)
    if (openToken != null) setOpen(true)
  }

  return (
    <Collapsible.Root open={open} onOpenChange={setOpen}>
      <Card>
        <CardHeader className="p-0">
          <Collapsible.Trigger
            className="group flex w-full cursor-pointer items-center justify-between px-6 py-4 text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
            aria-label={triggerAriaLabel}
          >
            <h2 className="text-title-sm">{title}</h2>
            <ChevronRight
              aria-hidden="true"
              className="size-4 shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-90"
            />
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
