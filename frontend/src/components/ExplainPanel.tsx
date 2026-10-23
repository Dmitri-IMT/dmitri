import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Dialog } from 'radix-ui'
import { explainAIContext } from '@/api/ai'
import { queryKeys } from '@/api/queryKeys'
import { useSession } from '@/auth/useSession'
import SidePanel from '@/components/SidePanel'
import WaitingState from '@/components/WaitingState'
import { Button } from '@/components/ui/button'
import useScanAnalysis from '@/hooks/useScanAnalysis'
import { useToast } from '@/hooks/useToast'
import useI18n from '@/i18n/useI18n'
import { TIME_KEY, WHO_KEY } from '@/lib/fixTask'
import { readAiAskError } from '@/api/readAiAskError'

export default function ExplainPanel({
  scope,
  contextId,
  scanId,
}: {
  scope: 'scan' | 'host'
  contextId: string
  scanId: string
}) {
  const { language, t } = useI18n()
  const { show } = useToast()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [cancelled, setCancelled] = useState(false)
  const [startedAt, setStartedAt] = useState(0)
  const requests = useRef(new Map<string, AbortController>())
  const actor = useSession().user?.user_id ?? 'anonymous'
  const key = [
    ...queryKeys.ai.explanation(scope, contextId, language, scanId),
    actor,
  ]
  const analysis = useScanAnalysis(scanId, open)
  const task =
    analysis.data?.status === 'completed'
      ? analysis.data.analysis.tasks[0]
      : undefined
  const query = useQuery({
    queryKey: key,
    queryFn: async () => {
      // Continue saving the answer when the panel closes or the language changes.
      // Only the explicit Cancel action aborts a generation.
      const controller = new AbortController()
      requests.current.set(language, controller)
      try {
        return await explainAIContext(
          { scope, context_id: contextId, language },
          controller.signal,
        )
      } finally {
        requests.current.delete(language)
      }
    },
    enabled: open && !cancelled,
    staleTime: Infinity,
    gcTime: Infinity,
    retry: false,
  })
  useEffect(() => {
    if (query.isError) show(readAiAskError(query.error, t('explain.error')))
  }, [query.isError, query.error, show, t])
  const title = t(scope === 'scan' ? 'explain.scan' : 'explain.host')
  const data = query.data
  return (
    <SidePanel
      title={title}
      testId={scope === 'scan' ? 'scan-explain-panel' : 'machine-explain-panel'}
      trigger={
        <Button
          variant="outline"
          data-testid={
            scope === 'scan' ? 'scan-explain-open' : 'machine-explain-open'
          }
        >
          {title}
        </Button>
      }
      onOpenChange={(value) => {
        setOpen(value)
        if (value) {
          setCancelled(false)
          setStartedAt(Date.now())
        }
      }}
    >
      <div className="flex min-h-0 flex-1 flex-col gap-8 overflow-y-auto p-6">
        {query.isFetching && (
          <WaitingState
            size="small"
            stage={t(
              scope === 'scan' ? 'explain.readingScan' : 'explain.readingHost',
            )}
            detail={t('ai.waiting.chatDetail')}
            startedAt={startedAt}
            cancelLabel={t('ai.waiting.cancel')}
            onCancel={() => {
              setCancelled(true)
              requests.current.get(language)?.abort()
              void queryClient.cancelQueries({ queryKey: key })
            }}
            testId="explain-waiting"
            cancelTestId="explain-cancel"
          />
        )}
        {(query.isError || cancelled) && !query.isFetching && (
          <Button
            variant="outline"
            className="self-start"
            onClick={() => {
              setCancelled(false)
              setStartedAt(Date.now())
              void query.refetch()
            }}
          >
            {t('explain.retry')}
          </Button>
        )}
        {data?.scope === 'scan' && (
          <>
            <section className="flex flex-col gap-3">
              <h3 className="text-title-xs">{t('explain.short')}</h3>
              <p>{data.explanation.in_short}</p>
            </section>
            <section className="flex flex-col gap-3">
              <h3 className="text-title-xs">{t('explain.meanings')}</h3>
              <ul className="flex list-disc flex-col gap-3 pl-4">
                {data.explanation.meanings.map((point) => (
                  <li key={point.lead}>
                    <strong>{point.lead}</strong> {point.text}
                  </li>
                ))}
              </ul>
            </section>
            <section className="flex flex-col gap-3">
              <h3 className="text-title-xs">{t('explain.notSeen')}</h3>
              <ul className="flex list-disc flex-col gap-3 pl-4">
                {data.explanation.not_seen.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </section>
            {task && (
              <div className="flex flex-col gap-2 rounded-control border border-rule p-4">
                <p className="font-semibold">
                  {t('explain.pointer', { title: task.title })}
                </p>
                <p className="text-body-sm text-ink-muted">
                  {t(WHO_KEY[task.who])} · {t(TIME_KEY[task.time])}
                </p>
              </div>
            )}
          </>
        )}
        {data?.scope === 'host' && (
          <>
            <section className="flex flex-col gap-3">
              <h3 className="text-title-xs">{t('machine.what')}</h3>
              <p>{data.explanation.what_it_is}</p>
            </section>
            <section className="flex flex-col gap-3">
              <h3 className="text-title-xs">{t('machine.problems')}</h3>
              <p>{data.explanation.problems}</p>
            </section>
          </>
        )}
      </div>
      <footer className="flex items-center justify-between gap-4 border-t border-rule px-6 py-4">
        <p className="text-caption-md text-ink-muted">{t('explain.footer')}</p>
        <Dialog.Close asChild>
          <Button
            variant="outline"
            onClick={() =>
              window.setTimeout(
                () => window.dispatchEvent(new Event('dmitri:assistant-open')),
                0,
              )
            }
          >
            {t('explain.ask')}
          </Button>
        </Dialog.Close>
      </footer>
    </SidePanel>
  )
}
