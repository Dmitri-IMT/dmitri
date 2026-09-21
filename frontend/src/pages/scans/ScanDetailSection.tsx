import type { ReactNode } from 'react'
import { Collapsible } from 'radix-ui'
import { Card, CardContent, CardHeader } from '@/components/ui/card'

function ScanDetailSection({
  title,
  children,
  defaultOpen = false,
  triggerAriaLabel,
}: {
  title: ReactNode
  children: ReactNode
  defaultOpen?: boolean
  triggerAriaLabel?: string
}) {
  return (
    <Collapsible.Root defaultOpen={defaultOpen}>
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
