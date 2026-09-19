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

type Props = {
  scope: AIContextScope
  contextId: string
  title?: string
  questionPlaceholder?: string
}

export default function ContextChat({
  scope,
  contextId,
  title = 'Pergunte sobre este contexto',
  questionPlaceholder = 'O que devo corrigir primeiro?',
}: Props) {
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

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = question.trim()
    if (trimmed.length < 3 || sending) return
    setSending(true)
    setError(null)
    try {
      const response = await askContextAI(scope, contextId, trimmed)
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
    } catch (caught) {
      setError(readContextChatError(caught))
    } finally {
      setSending(false)
    }
  }

  return (
    <Card data-testid="context-chat">
      <CardHeader>
        <h2 className="text-title-sm">{title}</h2>
        <p className="text-body-sm text-muted-foreground">
          A resposta usa somente as evidências disponíveis neste contexto.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
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
          {historyVisible ? 'Ocultar histórico' : 'Mostrar histórico'}
        </Button>
        <form className="flex flex-col gap-3" onSubmit={submit}>
          <label className="text-body-sm" htmlFor={`${scope}-context-question`}>
            Sua pergunta
          </label>
          <Textarea
            id={`${scope}-context-question`}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={questionPlaceholder}
            maxLength={1000}
          />
          <Button
            type="submit"
            size="sm"
            disabled={sending || question.trim().length < 3}
          >
            {sending ? 'Analisando...' : 'Perguntar'}
          </Button>
        </form>
        {historyVisible && loadingHistory && (
          <p className="text-body-sm text-muted-foreground">
            Carregando histórico...
          </p>
        )}
        {visibleMessages.map((message) => (
          <div
            className="flex flex-col gap-3 rounded-md border border-border p-4"
            key={message.message_id}
          >
            <div>
              <p className="text-body-sm font-medium">Sua pergunta</p>
              <p className="text-body-md">{message.question}</p>
            </div>
            <div>
              <p className="text-body-sm font-medium">Resposta</p>
              <p className="text-body-md">{message.answer}</p>
            </div>
            {message.uncertainties.length > 0 && (
              <div className="text-body-sm text-muted-foreground">
                <p className="font-medium">Limitações</p>
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

function readContextChatError(error: unknown): string {
  const response = (
    error as {
      response?: { data?: { error?: { code?: string; message?: string } } }
    }
  ).response
  if (
    response?.data?.error?.message &&
    ['ai_rate_limited', 'ai_context_too_large'].includes(
      response.data.error.code ?? '',
    )
  ) {
    return response.data.error.message
  }
  return 'Não foi possível obter uma resposta agora. Tente novamente.'
}
