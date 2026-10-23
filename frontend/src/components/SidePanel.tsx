import type { ReactNode } from 'react'
import { Dialog } from 'radix-ui'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import useI18n from '@/i18n/useI18n'

export default function SidePanel({
  title,
  trigger,
  testId,
  children,
  onOpenChange,
}: {
  title: string
  trigger: ReactNode
  testId: string
  children: ReactNode
  onOpenChange?: (open: boolean) => void
}) {
  const { t } = useI18n()
  return (
    <Dialog.Root onOpenChange={onOpenChange}>
      <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-ink/20" />
        <Dialog.Content
          data-testid={testId}
          aria-describedby={undefined}
          className="fixed inset-y-0 right-0 z-50 flex w-140 max-w-full flex-col border-l border-rule bg-card text-body-md outline-none"
        >
          <div className="flex items-center justify-between gap-4 border-b border-rule p-6">
            <Dialog.Title className="text-title-sm">{title}</Dialog.Title>
            <Dialog.Close asChild>
              <Button
                variant="ghost"
                size="icon"
                aria-label={t('common.close')}
              >
                <X aria-hidden="true" />
              </Button>
            </Dialog.Close>
          </div>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
