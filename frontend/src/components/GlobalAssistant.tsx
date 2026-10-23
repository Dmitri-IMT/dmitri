import { useEffect, useMemo, useState } from 'react'
import { useLocation } from 'react-router'
import { BotIcon } from 'lucide-react'
import ContextChat from '@/components/ContextChat'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogDescription,
} from '@/components/ui/dialog'
import useI18n from '@/i18n/useI18n'

function GlobalAssistant() {
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const { t } = useI18n()
  const context = useMemo(() => {
    const scan = location.pathname.match(/^\/scans\/([^/]+)$/)
    if (scan)
      return {
        scope: 'scan' as const,
        contextId: scan[1],
        label: t('ai.thisScan'),
      }
    const host = location.pathname.match(/^\/network\/([^/]+)$/)
    if (host)
      return {
        scope: 'host' as const,
        contextId: host[1],
        label: t('ai.thisHost'),
      }
    return null
  }, [location.pathname, t])
  useEffect(() => {
    const show = () => setOpen(true)
    window.addEventListener('dmitri:assistant-open', show)
    return () => window.removeEventListener('dmitri:assistant-open', show)
  }, [])
  if (!context) return null
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
      <DialogContent className="max-h-assistant-dialog overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-title-sm">
            {t('ai.askDmitri')}
          </DialogTitle>
          <DialogDescription className="text-caption-md text-ink-muted">
            {t('assistant.about', { label: context.label })}
          </DialogDescription>
        </DialogHeader>
        <ContextChat
          key={`${context.scope}:${context.contextId}`}
          scope={context.scope}
          contextId={context.contextId}
          compact
          questionPlaceholder={t('ai.placeholder')}
        />
      </DialogContent>
    </Dialog>
  )
}
export default GlobalAssistant
