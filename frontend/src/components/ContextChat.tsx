import { useEffect, useRef, useState } from 'react'
import { isCancel } from 'axios'
import {
  askContextAI,
  getContextAIHistory,
  type AIContextScope,
} from '@/api/ai'
import type { AIChatHistoryResponse } from '@/api/ai'
import ChatAnswer from '@/components/ChatAnswer'
import WaitingState from '@/components/WaitingState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { useToast } from '@/hooks/useToast'
import useI18n from '@/i18n/useI18n'
import { readAiAskError } from '@/api/readAiAskError'

type Props = {
  compact?: boolean
  scope: AIContextScope
  contextId: string
  title?: string
  questionPlaceholder?: string
  /** Renders a single ask button for this question instead of the free-text form. */
  presetQuestion?: string
  askLabel?: string
  askingLabel?: string
}

export default function ContextChat({
  scope,
  compact = false,
  contextId,
  title,
  questionPlaceholder,
  presetQuestion,
  askLabel,
  askingLabel,
}: Props) {
  const { language, t } = useI18n()
  const { show } = useToast()
  const oneShot = presetQuestion !== undefined
  const resolvedTitle = title ?? t('ai.askContext')
  const resolvedPlaceholder = questionPlaceholder ?? t('ai.placeholder')
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<AIChatHistoryResponse['data']>([])
  const [historyVisible, setHistoryVisible] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [sending, setSending] = useState(false)
  const [sentAt, setSentAt] = useState(0)
  const pendingAsk = useRef<AbortController | null>(null)
  const visibleMessages = historyVisible
    ? messages
    : messages.filter((m) => m.message_id.startsWith('local-'))
  const oneShotAnswered = oneShot && visibleMessages.length > 0

  useEffect(() => {
    if (!historyVisible) return
    let active = true
    getContextAIHistory(scope, contextId)
      .then((response) => {
        if (active) setMessages(response.data)
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) setLoadingHistory(false)
      })
    return () => {
      active = false
    }
  }, [contextId, historyVisible, scope])

  async function ask(asked: string) {
    if (asked.length < 3 || sending) return
    const controller = new AbortController()
    pendingAsk.current = controller
    setSentAt(Date.now())
    setSending(true)
    try {
      const response = await askContextAI(
        scope,
        contextId,
        asked,
        language,
        controller.signal,
      )
      setMessages((current) => [
        ...current,
        {
          message_id: `local-${Date.now()}`,
          question: asked,
          answer: response.answer,
          uncertainties: response.uncertainties,
          referenced_finding_ids: response.referenced_finding_ids,
          created_at: new Date().toISOString(),
        },
      ])
      setQuestion('')
    } catch (caught) {
      if (!isCancel(caught)) show(readAiAskError(caught, t('ai.genericError')))
    } finally {
      pendingAsk.current = null
      setSending(false)
    }
  }

  useEffect(() => () => pendingAsk.current?.abort(), [])

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void ask(question.trim())
  }

  return (
    <Card
      data-testid="context-chat"
      className={compact ? 'border-0 bg-transparent shadow-none' : undefined}
    >
      {!compact && (
        <CardHeader>
          <h2 className="text-title-sm">{resolvedTitle}</h2>
          <p className="text-body-sm text-muted-foreground">
            {t('ai.contextHint')}
          </p>
        </CardHeader>
      )}
      <CardContent className="flex flex-col gap-4">
        {!oneShot && (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="self-start"
            aria-expanded={historyVisible}
            onClick={() => {
              if (!historyVisible) setLoadingHistory(true)
              setHistoryVisible((visible) => !visible)
            }}
          >
            {historyVisible ? t('ai.hideHistory') : t('ai.showHistory')}
          </Button>
        )}
        {oneShot ? (
          !oneShotAnswered && (
            <Button
              type="button"
              size="sm"
              className="self-start"
              onClick={() => void ask(presetQuestion)}
              disabled={sending}
            >
              {sending
                ? (askingLabel ?? t('ai.asking'))
                : (askLabel ?? t('ai.ask'))}
            </Button>
          )
        ) : (
          <form
            className={cn(
              'flex gap-3',
              compact
                ? 'order-last items-end border-t border-rule pt-4'
                : 'flex-col',
            )}
            onSubmit={submit}
          >
            <label
              className={compact ? 'sr-only' : 'text-body-sm'}
              htmlFor={`${scope}-context-question`}
            >
              {t('ai.question')}
            </label>
            {compact ? (
              <Input
                id={`${scope}-context-question`}
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder={resolvedPlaceholder}
                maxLength={1000}
                disabled={sending}
              />
            ) : (
              <Textarea
                id={`${scope}-context-question`}
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder={resolvedPlaceholder}
                maxLength={1000}
                disabled={sending}
              />
            )}
            <Button
              type="submit"
              size="sm"
              className="self-start"
              disabled={sending || question.trim().length < 3}
            >
              {sending ? t('ai.asking') : t('ai.ask')}
            </Button>
          </form>
        )}
        {sending && (
          <WaitingState
            size="small"
            stage={t('ai.waiting.chatStage')}
            detail={t('ai.waiting.chatDetail')}
            startedAt={sentAt}
            cancelLabel={t('ai.waiting.cancel')}
            onCancel={() => pendingAsk.current?.abort()}
            testId="assistant-waiting"
            cancelTestId="assistant-cancel"
          />
        )}
        {historyVisible && loadingHistory && (
          <p className="text-body-sm text-muted-foreground">
            {t('ai.loadingHistory')}
          </p>
        )}
        {visibleMessages.map((message) => (
          <div
            className="flex flex-col gap-4"
            aria-live="polite"
            key={message.message_id}
          >
            {!oneShot && (
              <div className="max-w-100 self-end rounded-lg border border-rule bg-canvas px-4 py-3 text-body-md">
                {message.question}
              </div>
            )}
            <div className="max-w-120 text-body-md">
              <ChatAnswer text={message.answer} />
            </div>
            {message.uncertainties.length > 0 && (
              <div className="text-body-sm text-muted-foreground">
                <p className="font-medium">{t('ai.limitations')}</p>
                <ul className="list-disc pl-4">
                  {message.uncertainties.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
