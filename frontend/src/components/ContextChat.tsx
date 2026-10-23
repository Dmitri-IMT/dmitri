import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import {
  useInfiniteQuery,
  useMutation,
  useMutationState,
  useQueryClient,
  type InfiniteData,
} from '@tanstack/react-query'
import { Popover } from 'radix-ui'
import { ArrowUpIcon, HistoryIcon, SquarePenIcon } from 'lucide-react'
import { isCancel } from 'axios'
import {
  askContextAI,
  getAIConversations,
  getContextAIHistory,
  type AIContextScope,
  type AIChatHistoryResponse,
  type AILanguage,
} from '@/api/ai'
import { queryKeys } from '@/api/queryKeys'
import { useSession } from '@/auth/useSession'
import ChatAnswer from '@/components/ChatAnswer'
import WaitingState from '@/components/WaitingState'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { useToast } from '@/hooks/useToast'
import useI18n from '@/i18n/useI18n'
import { readAiAskError } from '@/api/readAiAskError'

type Ask = {
  question: string
  conversationId: string
  language: AILanguage
  controller: AbortController
  startedAt: number
}

type Props = {
  compact?: boolean
  scope: AIContextScope
  contextId: string
  title?: string
  heading?: ReactNode
  closeButton?: ReactNode
  conversationId?: string | null
  onConversationChange?: (id: string | null) => void
  questionPlaceholder?: string
  presetQuestion?: string
  askLabel?: string
  askingLabel?: string
}

export default function ContextChat({
  scope,
  compact = false,
  contextId,
  title,
  heading,
  closeButton,
  conversationId: controlledId,
  onConversationChange,
  questionPlaceholder,
  presetQuestion,
  askLabel,
  askingLabel,
}: Props) {
  const { language, t } = useI18n()
  const { show } = useToast()
  const queryClient = useQueryClient()
  const actor = useSession().user?.user_id ?? 'anonymous'
  const inputId = useId()
  const bottom = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const [localId, setLocalId] = useState<string | null>(null)
  const conversationId = controlledId === undefined ? localId : controlledId
  const activeConversation = useRef(conversationId)
  const [question, setQuestion] = useState('')
  const [historyOpen, setHistoryOpen] = useState(false)
  useEffect(() => {
    activeConversation.current = conversationId
  }, [conversationId])
  const oneShot = presetQuestion !== undefined
  const historyKey = [...queryKeys.ai.conversations(scope, contextId), actor]
  const messageKey = [
    ...queryKeys.ai.chat(scope, contextId, conversationId),
    actor,
  ]
  const mutationKey = [...queryKeys.ai.asking(scope, contextId), actor]
  const history = useInfiniteQuery({
    queryKey: historyKey,
    queryFn: ({ pageParam }) => getAIConversations(scope, contextId, pageParam),
    initialPageParam: 1,
    getNextPageParam: (last, pages) =>
      last.has_more ? pages.length + 1 : undefined,
    enabled: historyOpen,
    staleTime: 30_000,
  })
  const transcript = useInfiniteQuery({
    queryKey: messageKey,
    queryFn: ({ pageParam }) =>
      getContextAIHistory(scope, contextId, conversationId!, pageParam),
    initialPageParam: 1,
    getNextPageParam: (last, pages) =>
      last.has_more ? pages.length + 1 : undefined,
    enabled: conversationId !== null,
    staleTime: Infinity,
  })
  const messages = [
    ...new Map(
      (
        transcript.data?.pages.toReversed().flatMap((page) => page.data) ?? []
      ).map((message) => [message.message_id, message]),
    ).values(),
  ]
  const pending = useMutationState<Ask>({
    filters: { mutationKey, status: 'pending' },
    select: (mutation) => mutation.state.variables as Ask,
  }).find((ask) => ask.conversationId === conversationId)
  const mutation = useMutation({
    mutationKey,
    mutationFn: (asked: Ask) =>
      askContextAI(
        scope,
        contextId,
        asked.question,
        asked.language,
        asked.controller.signal,
        asked.conversationId,
      ),
    onSuccess: async (saved) => {
      await queryClient.cancelQueries({
        queryKey: [
          ...queryKeys.ai.chat(scope, contextId, saved.conversation_id),
          actor,
        ],
      })
      queryClient.setQueryData<InfiniteData<AIChatHistoryResponse>>(
        [...queryKeys.ai.chat(scope, contextId, saved.conversation_id), actor],
        (current) =>
          current
            ? {
                ...current,
                pages: current.pages.map((page, index) =>
                  index === 0
                    ? {
                        ...page,
                        data: [
                          ...page.data.filter(
                            (message) =>
                              message.message_id !== saved.message_id,
                          ),
                          saved,
                        ],
                      }
                    : page,
                ),
              }
            : { pages: [{ data: [saved], has_more: false }], pageParams: [1] },
      )
      void queryClient.invalidateQueries({ queryKey: historyKey })
    },
    onError: (error, asked) => {
      if (!isCancel(error)) {
        show(readAiAskError(error, t('ai.genericError')))
        if (activeConversation.current === asked.conversationId)
          setQuestion((current) => current || asked.question)
      }
    },
  })

  useEffect(() => {
    const error = history.error ?? transcript.error
    if (error) show(readAiAskError(error, t('assistant.historyError')))
  }, [history.error, transcript.error, show, t])
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: 'nearest' })
  }, [messages.length, pending?.startedAt])

  function selectConversation(id: string | null) {
    setLocalId(id)
    onConversationChange?.(id)
    setQuestion('')
    setHistoryOpen(false)
  }
  function ask(asked: string) {
    if (asked.length < 3 || pending) return
    const id = conversationId ?? crypto.randomUUID()
    if (!conversationId) selectConversation(id)
    setQuestion('')
    mutation.mutate({
      question: asked,
      conversationId: id,
      language,
      controller: new AbortController(),
      startedAt: Date.now(),
    })
  }
  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    ask(question.trim())
  }
  const date = (value: string) =>
    new Intl.DateTimeFormat(language, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value))

  return (
    <section
      data-testid="context-chat"
      className={cn(
        'flex min-h-0 flex-1 flex-col',
        !compact && 'rounded-lg border border-rule bg-card',
      )}
    >
      <header className="flex items-center justify-between gap-4 border-b border-rule px-6 py-4">
        {heading ?? (
          <h2 className="text-title-sm">{title ?? t('ai.askDmitri')}</h2>
        )}
        <div className="flex items-center gap-1">
          {!oneShot && (
            <>
              <Popover.Root open={historyOpen} onOpenChange={setHistoryOpen}>
                <Popover.Trigger asChild>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label={t('assistant.history')}
                  >
                    <HistoryIcon aria-hidden="true" />
                  </Button>
                </Popover.Trigger>
                <Popover.Portal>
                  <Popover.Content
                    align="end"
                    sideOffset={8}
                    className="z-50 flex max-h-96 w-80 flex-col gap-4 overflow-y-auto rounded-lg border border-rule bg-card p-4 text-body-md text-ink shadow-md"
                    aria-label={t('assistant.history')}
                  >
                    <h3 className="text-title-xs">{t('assistant.history')}</h3>
                    {history.isPending && (
                      <p className="text-body-sm text-ink-muted">
                        {t('ai.loadingHistory')}
                      </p>
                    )}
                    {history.isError && (
                      <Button
                        variant="outline"
                        onClick={() => void history.refetch()}
                      >
                        {t('explain.retry')}
                      </Button>
                    )}
                    {history.data?.pages.every(
                      (page) => page.data.length === 0,
                    ) && (
                      <p className="text-body-sm text-ink-muted">
                        {t('assistant.noHistory')}
                      </p>
                    )}
                    <div className="flex flex-col gap-1">
                      {history.data?.pages
                        .flatMap((page) => page.data)
                        .map((chat) => (
                          <Button
                            key={chat.conversation_id}
                            variant="ghost"
                            className="h-auto min-w-0 flex-col items-start gap-1 whitespace-normal px-3 py-3 text-left"
                            onClick={() =>
                              selectConversation(chat.conversation_id)
                            }
                          >
                            <span className="line-clamp-2 text-body-sm">
                              {chat.title}
                            </span>
                            <time
                              className="text-caption-md font-normal text-ink-muted"
                              dateTime={chat.updated_at}
                            >
                              {date(chat.updated_at)}
                            </time>
                          </Button>
                        ))}
                    </div>
                    {history.hasNextPage && (
                      <Button
                        variant="outline"
                        disabled={history.isFetchingNextPage}
                        onClick={() => void history.fetchNextPage()}
                      >
                        {t('assistant.moreHistory')}
                      </Button>
                    )}
                  </Popover.Content>
                </Popover.Portal>
              </Popover.Root>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={t('assistant.newChat')}
                onClick={() => {
                  selectConversation(null)
                  input.current?.focus()
                }}
              >
                <SquarePenIcon aria-hidden="true" />
              </Button>
            </>
          )}
          {closeButton}
        </div>
      </header>
      <div
        className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto px-6 py-6"
        data-testid="chat-transcript"
        aria-live="polite"
      >
        {transcript.isFetching && messages.length === 0 && (
          <p className="text-body-sm text-ink-muted">
            {t('ai.loadingHistory')}
          </p>
        )}
        {transcript.isError && (
          <Button
            variant="outline"
            className="self-start"
            onClick={() => void transcript.refetch()}
          >
            {t('explain.retry')}
          </Button>
        )}
        {transcript.hasNextPage && (
          <Button
            variant="outline"
            className="self-center"
            disabled={transcript.isFetchingNextPage}
            onClick={() => void transcript.fetchNextPage()}
          >
            {t('assistant.olderMessages')}
          </Button>
        )}
        {messages.length === 0 &&
          !pending &&
          !transcript.isFetching &&
          !oneShot && (
            <p className="text-body-md text-ink-muted">
              {t('assistant.empty')}
            </p>
          )}
        {messages.map((message) => (
          <div key={message.message_id} className="flex flex-col gap-4">
            <time
              className="self-center text-caption-md text-ink-muted"
              dateTime={message.created_at}
            >
              {date(message.created_at)}
            </time>
            {!oneShot && (
              <div className="max-w-prose self-end rounded-lg bg-canvas px-4 py-3 text-body-md">
                {message.question}
              </div>
            )}
            <div className="flex flex-col gap-2 text-body-md">
              <p className="text-caption-md font-semibold">
                {t('ai.assistant')}
              </p>
              <ChatAnswer text={message.answer} />
            </div>
            {message.uncertainties.length > 0 && (
              <ul className="list-disc pl-4 text-body-sm text-ink-muted">
                {message.uncertainties.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            )}
          </div>
        ))}
        {pending && (
          <>
            {!oneShot && (
              <div className="max-w-prose self-end rounded-lg bg-canvas px-4 py-3 text-body-md">
                {pending.question}
              </div>
            )}
            <WaitingState
              size="small"
              stage={t('ai.waiting.chatStage')}
              detail={t('ai.waiting.chatDetail')}
              startedAt={pending.startedAt}
              cancelLabel={t('ai.waiting.cancel')}
              onCancel={() => pending.controller.abort()}
              testId="assistant-waiting"
              cancelTestId="assistant-cancel"
            />
          </>
        )}
        <div ref={bottom} />
      </div>
      {oneShot ? (
        messages.length === 0 && (
          <div className="px-6 pb-6">
            <Button
              size="sm"
              onClick={() => ask(presetQuestion)}
              disabled={Boolean(pending)}
            >
              {pending
                ? (askingLabel ?? t('ai.asking'))
                : (askLabel ?? t('ai.ask'))}
            </Button>
          </div>
        )
      ) : (
        <form
          className="flex flex-col gap-3 border-t border-rule p-6"
          onSubmit={submit}
        >
          <label
            className={compact ? 'sr-only' : 'text-body-sm'}
            htmlFor={inputId}
          >
            {t('ai.question')}
          </label>
          <Textarea
            ref={input}
            id={inputId}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={questionPlaceholder ?? t('ai.placeholder')}
            maxLength={1000}
            rows={2}
            disabled={Boolean(pending)}
          />
          <Button
            type="submit"
            className="self-end text-body-sm"
            disabled={Boolean(pending) || question.trim().length < 3}
            aria-label={t('ai.ask')}
          >
            <ArrowUpIcon aria-hidden="true" />
            {t('ai.ask')}
          </Button>
        </form>
      )}
    </section>
  )
}
