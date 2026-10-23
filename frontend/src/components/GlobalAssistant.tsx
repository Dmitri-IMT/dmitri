import { useEffect, useMemo, useState } from 'react'
import { useLocation } from 'react-router'
import { BotIcon, XIcon } from 'lucide-react'
import ContextChat from '@/components/ContextChat'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogClose,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
} from '@/components/ui/dialog'
import useI18n from '@/i18n/useI18n'

function GlobalAssistant() {
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [conversations, setConversations] = useState<
    Record<string, string | null>
  >({})
  const { t } = useI18n()
  const context = useMemo(() => {
    const scan = location.pathname.match(/^\/scans\/([^/]+)$/)
    if (scan)
      return {
        scope: 'scan' as const,
        contextId: scan[1],
      }
    const host = location.pathname.match(/^\/network\/([^/]+)$/)
    if (host)
      return {
        scope: 'host' as const,
        contextId: host[1],
      }
    return null
  }, [location.pathname])
  useEffect(() => {
    const show = () => setOpen(true)
    window.addEventListener('dmitri:assistant-open', show)
    return () => window.removeEventListener('dmitri:assistant-open', show)
  }, [])
  if (!context) return null
  const contextKey = `${context.scope}:${context.contextId}`
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="outline"
          aria-label={t('ai.openAssistant')}
          data-testid="top-bar-assistant"
        >
          <BotIcon aria-hidden="true" />
          {t('ai.assistant')}
        </Button>
      </DialogTrigger>
      <DialogContent
        showCloseButton={false}
        className="flex h-160 max-h-assistant-dialog flex-col gap-0 overflow-hidden p-0 text-body-md sm:max-w-2xl"
      >
        <DialogDescription className="sr-only">
          {t('assistant.empty')}
        </DialogDescription>
        <ContextChat
          key={contextKey}
          scope={context.scope}
          contextId={context.contextId}
          conversationId={conversations[contextKey] ?? null}
          onConversationChange={(id) =>
            setConversations((current) => ({ ...current, [contextKey]: id }))
          }
          heading={
            <DialogTitle className="text-title-sm">
              {t('ai.askDmitri')}
            </DialogTitle>
          }
          closeButton={
            <DialogClose asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={t('common.close')}
              >
                <XIcon aria-hidden="true" />
              </Button>
            </DialogClose>
          }
          compact
          questionPlaceholder={t('ai.placeholder')}
        />
      </DialogContent>
    </Dialog>
  )
}
export default GlobalAssistant
