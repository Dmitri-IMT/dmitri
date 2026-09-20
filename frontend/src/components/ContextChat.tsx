import { useEffect, useState } from 'react'
import {
  askContextAI,
  getContextAIHistory,
  type AIContextScope,
} from '@/api/ai'
import type { AIChatHistoryResponse } from '@/api/ai'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import useI18n from '@/i18n/useI18n'
import { readAiAskError } from '@/api/readAiAskError'

type Props = {
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
  contextId,
  title,
  questionPlaceholder,
  presetQuestion,
  askLabel,
  askingLabel,
}: Props) {
  const { language, t } = useI18n()
  const oneShot = presetQuestion !== undefined
  const resolvedTitle = title ?? t('ai.askContext')
  const resolvedPlaceholder = questionPlaceholder ?? t('ai.placeholder')
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<AIChatHistoryResponse['data']>([])
  const [historyVisible, setHistoryVisible] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const visibleMessages = historyVisible
    ? messages
    : messages.filter((m) => m.message_id.startsWith('local-'))

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
    setSending(true)
    setError(null)
    try {
      const response = await askContextAI(scope, contextId, asked, language)
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
      setError(readAiAskError(caught, t('ai.genericError')))
    } finally {
      setSending(false)
    }
  }

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void ask(question.trim())
  }

  return (
    <Card data-testid="context-chat">
      <CardHeader>
        <h2 className="text-title-sm">{resolvedTitle}</h2>
        <p className="text-body-sm text-muted-foreground">
          {t('ai.contextHint')}
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {!oneShot && (
          <Button
            type="button"
            variant="outline"
            size="sm"
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
          <Button
            type="button"
            size="sm"
            onClick={() => void ask(presetQuestion)}
            disabled={sending}
          >
            {sending
              ? (askingLabel ?? t('ai.asking'))
              : (askLabel ?? t('ai.ask'))}
          </Button>
        ) : (
          <form className="flex flex-col gap-3" onSubmit={submit}>
            <label
              className="text-body-sm"
              htmlFor={`${scope}-context-question`}
            >
              {t('ai.question')}
            </label>
            <Textarea
              id={`${scope}-context-question`}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder={resolvedPlaceholder}
              maxLength={1000}
            />
            <Button
              type="submit"
              size="sm"
              disabled={sending || question.trim().length < 3}
            >
              {sending ? t('ai.asking') : t('ai.ask')}
            </Button>
          </form>
        )}
        {historyVisible && loadingHistory && (
          <p className="text-body-sm text-muted-foreground">
            {t('ai.loadingHistory')}
          </p>
        )}
        {visibleMessages.map((message) => (
          <div
            className="flex flex-col gap-3 rounded-md border border-border p-4"
            aria-live="polite"
            key={message.message_id}
          >
            {!oneShot && (
              <div>
                <p className="text-body-sm font-medium">{t('ai.question')}</p>
                <p className="text-body-md">{message.question}</p>
              </div>
            )}
            <div>
              <p className="text-body-sm font-medium">{t('ai.answer')}</p>
              <p className="text-body-md">{message.answer}</p>
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
        {error && (
          <p className="text-body-sm text-destructive" role="alert">
            {error}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
