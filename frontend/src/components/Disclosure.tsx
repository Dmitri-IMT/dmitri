import { useId, useState, type ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'
import { Collapsible } from 'radix-ui'
import { Button } from '@/components/ui/button'

type DisclosureProps = {
  label: string
  children: ReactNode
  testId: string
  caretTestId: string
  defaultOpen?: boolean
}

function Disclosure({
  label,
  children,
  testId,
  caretTestId,
  defaultOpen = false,
}: DisclosureProps) {
  const [open, setOpen] = useState(defaultOpen)
  // Radix drops `aria-controls` from the trigger while collapsed. Own the id here so the
  // trigger stays linked to its content in both states.
  const contentId = useId()

  return (
    <Collapsible.Root
      open={open}
      onOpenChange={setOpen}
      className="flex flex-col items-start gap-1"
    >
      <Collapsible.Trigger asChild aria-controls={contentId}>
        <Button
          variant="link"
          data-testid={testId}
          className="group h-auto cursor-pointer justify-start gap-1 p-0 font-normal text-muted-foreground underline-offset-4 outline-none hover:text-foreground hover:underline focus-visible:underline focus-visible:ring-3 focus-visible:ring-ring/50 active:translate-y-px"
        >
          <ChevronRight
            aria-hidden="true"
            data-testid={caretTestId}
            className="size-3 shrink-0 transition-transform group-data-[state=open]:rotate-90"
          />
          <span className="text-body-md">{label}</span>
        </Button>
      </Collapsible.Trigger>
      <Collapsible.Content forceMount asChild id={contentId} hidden={!open}>
        {children}
      </Collapsible.Content>
    </Collapsible.Root>
  )
}

export default Disclosure
