import { useEffect, useState } from 'react'
import { askScanAI, getScanAIChat } from '@/api/scans'
import type { AIChatHistoryResponse } from '@/api/scans'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import useI18n from '@/i18n/useI18n'

function ScanChat({ scanId }: { scanId: string }) {
  const { language, t } = useI18n()
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<AIChatHistoryResponse['data']>([])
  const [isHistoryVisible, setIsHistoryVisible] = useState(false)
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isSending, setIsSending] = useState(false)
  const visibleMessages = messages.filter(
    (message) => isHistoryVisible || message.message_id.startsWith('local-'),
  )

  useEffect(() => {
    if (!isHistoryVisible) return
    let active = true
    getScanAIChat(scanId)
      .then((response) => {
        if (active) setMessages(response.data)
      })
      .catch(() => {
        // History is supplementary; the user can still ask a new question.
      })
      .finally(() => {
        if (active) setIsLoadingHistory(false)
      })
    return () => {
      active = false
    }
  }, [isHistoryVisible, scanId])

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = question.trim()
    if (trimmed.length < 3 || isSending) return
    setIsSending(true)
    setError(null)
    try {
      const response = await askScanAI(scanId, trimmed, language)
      setMessages((current) => [
        ...current,
        {
          message_id: `local-${Date.now()}`,
          question: trimmed,
          answer: response.answer,
          uncertainties: response.uncertainties,
          referenced_finding_ids: response.referenced_finding_ids,
          created_at: new Date().toISOString(),
        },
      ])
      setQuestion('')
    } catch (caughtError) {
      setError(readChatErrorMessage(caughtError, t))
    } finally {
      setIsSending(false)
    }
  }

  return (
    <Card data-testid="scan-chat">
      <CardHeader>
        <h2 className="text-title-sm">{t('ai.askAboutScan')}</h2>
        <p className="text-body-sm text-muted-foreground">
          {t('ai.contextHint')}
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-expanded={isHistoryVisible}
          onClick={() => {
            setIsHistoryVisible((visible) => !visible)
            if (!isHistoryVisible) setIsLoadingHistory(true)
          }}
        >
          {isHistoryVisible ? t('ai.hideHistory') : t('ai.showHistory')}
        </Button>
        <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
          <label className="text-body-sm" htmlFor="scan-question">
            {t('ai.question')}
          </label>
          <Textarea
            id="scan-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={t('ai.placeholder')}
            maxLength={1000}
          />
          <Button
            type="submit"
            size="sm"
            disabled={isSending || question.trim().length < 3}
          >
            {isSending ? t('ai.asking') : t('ai.ask')}
          </Button>
        </form>
        {isHistoryVisible && isLoadingHistory && (
          <p className="text-body-sm text-muted-foreground">
            {t('ai.loadingHistory')}
          </p>
        )}
        {visibleMessages.map((message) => (
          <div
            className="flex flex-col gap-3 rounded-md border border-border p-4"
            key={message.message_id}
            aria-live="polite"
          >
            <div>
              <p className="text-body-sm font-medium">{t('ai.question')}</p>
              <p className="text-body-md">{message.question}</p>
            </div>
            <div>
              <p className="text-body-sm font-medium">{t('ai.answer')}</p>
              <p className="text-body-md">{message.answer}</p>
            </div>
            {message.referenced_finding_ids.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {message.referenced_finding_ids.map((findingId, index) => (
                  <a
                    className="text-body-sm text-primary underline underline-offset-2"
                    href={`/scans/${scanId}?finding=${findingId}`}
                    key={findingId}
                  >
                    {t('ai.viewFinding', { index: index + 1 })}
                  </a>
                ))}
              </div>
            )}
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

function readChatErrorMessage(
  error: unknown,
  translate: (key: 'ai.genericError') => string,
): string {
  const response = (
    error as {
      response?: { data?: { error?: { code?: string; message?: string } } }
    }
  ).response
  if (
    (response?.data?.error?.code === 'ai_rate_limited' ||
      response?.data?.error?.code === 'ai_context_too_large') &&
    response.data.error.message
  ) {
    return response.data.error.message
  }
  return translate('ai.genericError')
}

export default ScanChat
