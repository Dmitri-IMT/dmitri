import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import { ChevronRight } from 'lucide-react'
import {
  getScanAnalysis,
  requestScanAnalysis,
  type ScanAIAnalysisResponse,
} from '@/api/scans'
import { queryKeys } from '@/api/queryKeys'
import WaitingState from '@/components/WaitingState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { useToast } from '@/hooks/useToast'
import type { components } from '@/types/openapi'
import useI18n from '@/i18n/useI18n'
import { TIME_KEY, WHO_KEY, machineName } from '@/lib/fixTask'
import { cn } from '@/lib/utils'

type FindingRecord = components['schemas']['FindingRecord']
type FixTask = components['schemas']['AIFixTask']
type QueuedAnalysis = components['schemas']['ScanAIAnalysisQueued']

const ANALYSIS_POLL_INTERVAL_MS = 3_000
const ANALYSIS_POLL_MAX_MS = 20 * 60 * 1_000
const FALLBACK_COUNT = 3

function waitingForAnalysis(status: ScanAIAnalysisResponse['status']): boolean {
  return status === 'pending' || status === 'processing'
}

function AnalysisWaiting({ analysis }: { analysis: QueuedAnalysis }) {
  const { t } = useI18n()
  const progress = analysis.progress ?? null
  const stage =
    progress === null
      ? analysis.status === 'pending'
        ? t('ai.waiting.queuedStage')
        : t('ai.waiting.groupsStage')
      : t(`ai.waiting.${progress.stage}Stage`)
  const detail =
    progress?.stage === 'groups' && progress.total > 0
      ? t('ai.waiting.groupDetail', {
          n: Math.min(progress.done + 1, progress.total),
          m: progress.total,
        })
      : t('ai.waiting.scanDetail')
  return (
    <WaitingState
      size="large"
      stage={stage}
      detail={detail}
      startedAt={Date.parse(analysis.created_at)}
      progress={
        progress !== null && progress.stage !== 'fixes'
          ? { done: progress.done, total: progress.total }
          : undefined
      }
      testId="todo-waiting"
    />
  )
}

function TodoCard({
  title,
  aside,
  testId,
  children,
}: {
  title: string
  aside?: string
  testId: string
  children: React.ReactNode
}) {
  return (
    <Card data-testid={testId}>
      <CardHeader className="flex flex-row items-baseline justify-between gap-4">
        <h2 className="text-title-sm">{title}</h2>
        {aside && (
          <p
            className="text-caption-md text-ink-muted"
            data-testid="todo-count"
          >
            {aside}
          </p>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-4">{children}</CardContent>
    </Card>
  )
}

function TaskRow({
  task,
  findingsById,
  open,
  onToggle,
}: {
  task: FixTask
  findingsById: Map<string, FindingRecord>
  open: boolean
  onToggle: () => void
}) {
  const { t } = useI18n()
  const bodyId = `todo-task-body-${task.rank}`
  const machines = new Map<string, string>()
  for (const id of task.finding_ids) {
    const finding = findingsById.get(id)
    const name = finding ? machineName(finding) : null
    if (finding?.host_id && name) machines.set(finding.host_id, name)
  }
  return (
    <li
      id={`todo-task-${task.rank}`}
      data-testid={`todo-task-${task.rank}`}
      className="flex flex-col gap-2 border-t border-rule py-4 last:border-b"
    >
      <div className="flex items-center gap-4">
        <span
          aria-hidden="true"
          className={cn(
            'flex size-7 shrink-0 items-center justify-center rounded-full border border-ink text-caption-md font-semibold',
            task.rank === 1 ? 'bg-ink text-card' : 'text-ink',
          )}
        >
          {task.rank}
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <p className="text-body-md font-semibold text-ink">{task.title}</p>
          <p className="text-caption-md text-ink-muted">
            {t(WHO_KEY[task.who])} · {t(TIME_KEY[task.time])} ·{' '}
            {t('todo.fixesProblems', { count: task.finding_ids.length })}
          </p>
        </div>
        <div className="flex w-30 shrink-0 flex-col">
          <p className="text-caption-md text-ink-muted">{t('todo.risk')}</p>
          <p className="text-body-md font-semibold text-ink">
            {task.highest_risk_score == null
              ? '—'
              : Math.round(task.highest_risk_score)}
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-expanded={open}
          aria-controls={bodyId}
          aria-label={open ? t('todo.hideSteps') : t('todo.showSteps')}
          data-testid={`todo-task-toggle-${task.rank}`}
          onClick={onToggle}
        >
          <ChevronRight
            aria-hidden="true"
            className={cn('size-4 transition-transform', open && 'rotate-90')}
          />
        </Button>
      </div>
      <div
        id={bodyId}
        hidden={!open}
        className="flex flex-col gap-2 pl-12 text-body-md"
      >
        <ol className="list-decimal pl-4">
          {task.steps.map((step, index) => (
            <li key={index}>{step}</li>
          ))}
        </ol>
        {task.sources.length > 0 && (
          <p className="text-body-sm text-ink-muted">
            {t('todo.sources')}{' '}
            {task.sources.map((source, index) => (
              <span key={source.url}>
                {index > 0 && ', '}
                <Button
                  asChild
                  variant="link"
                  className="h-auto p-0 text-body-sm"
                >
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noreferrer noopener"
                  >
                    {source.name}
                  </a>
                </Button>
              </span>
            ))}
          </p>
        )}
        {(task.fallback || machines.size > 0) && (
          <p className="text-body-sm text-ink-muted">
            {task.fallback}
            {task.fallback && machines.size > 0 && ' · '}
            {[...machines].map(([hostId, name], index) => (
              <span key={hostId}>
                {index > 0 && ', '}
                <Button
                  asChild
                  variant="link"
                  className="h-auto p-0 text-body-sm"
                >
                  <Link to={`/network/${hostId}`}>{name}</Link>
                </Button>
              </span>
            ))}
          </p>
        )}
      </div>
    </li>
  )
}

function TodoList({
  scanId,
  findings,
}: {
  scanId: string
  findings: FindingRecord[]
}) {
  const { language, t } = useI18n()
  const { show } = useToast()
  const queryClient = useQueryClient()
  const pollingStartedAtRef = useRef<number | null>(null)
  const [isRequesting, setIsRequesting] = useState(false)
  const [openRanks, setOpenRanks] = useState<Set<number>>(() => new Set([1]))

  const query = useQuery({
    queryKey: queryKeys.scans.analysis(scanId, language),
    queryFn: () => getScanAnalysis(scanId, language),
    enabled: scanId !== '',
    retry: false,
    refetchInterval: (currentQuery) => {
      const status = currentQuery.state.data?.status
      if (!status || !waitingForAnalysis(status)) {
        pollingStartedAtRef.current = null
        return false
      }
      if (pollingStartedAtRef.current === null) {
        pollingStartedAtRef.current = Date.now()
      }
      if (Date.now() - pollingStartedAtRef.current >= ANALYSIS_POLL_MAX_MS) {
        return false
      }
      return ANALYSIS_POLL_INTERVAL_MS
    },
  })

  useEffect(() => {
    if (query.isError) show(t('todo.loadFailed'))
  }, [query.isError, show, t])

  async function handleRequest() {
    setIsRequesting(true)
    try {
      const data = await requestScanAnalysis(scanId, language)
      queryClient.setQueryData(queryKeys.scans.analysis(scanId, language), data)
    } catch (error) {
      if (isAxiosError(error) && error.response?.status === 409) {
        await query.refetch()
      } else {
        show(t('todo.requestFailed'))
      }
    } finally {
      setIsRequesting(false)
    }
  }

  if (query.isPending) return null

  const requestButton = (label: string, testId: string) => (
    <Button
      type="button"
      className="self-start"
      data-testid={testId}
      disabled={isRequesting}
      onClick={() => void handleRequest()}
    >
      {label}
    </Button>
  )

  const data = query.isError ? undefined : query.data
  if (data === undefined || data.status === 'unavailable') {
    const top = [...findings]
      .sort((a, b) => (b.risk_score ?? -1) - (a.risk_score ?? -1))
      .slice(0, FALLBACK_COUNT)
    return (
      <TodoCard title={t('todo.fallbackTitle')} testId="todo-fallback">
        {top.length === 0 ? (
          <p className="text-body-md">{t('todo.nothingToFix')}</p>
        ) : (
          <>
            <p className="text-body-sm text-ink-muted">
              {t('todo.fallbackLead', { count: top.length })}
            </p>
            <ol className="flex list-decimal flex-col gap-2 pl-4 text-body-md">
              {top.map((finding) => (
                <li key={finding.finding_id}>
                  {machineName(finding) && (
                    <span className="font-semibold">
                      {machineName(finding)}
                    </span>
                  )}
                  {machineName(finding) && ' — '}
                  {finding.recommendation}
                </li>
              ))}
            </ol>
          </>
        )}
      </TodoCard>
    )
  }

  switch (data.status) {
    case 'not_requested':
      return (
        <TodoCard title={t('todo.title')} testId="todo-not-requested">
          <p className="text-body-md">{t('todo.notRequested')}</p>
          {requestButton(t('todo.makeList'), 'todo-request')}
        </TodoCard>
      )
    case 'pending':
    case 'processing':
      return (
        <TodoCard title={t('todo.title')} testId="todo-list-waiting">
          <AnalysisWaiting analysis={data} />
          <p className="text-body-sm text-ink-muted">{t('todo.leavePage')}</p>
        </TodoCard>
      )
    case 'failed':
      return (
        <TodoCard title={t('todo.title')} testId="todo-failed">
          <p className="text-body-md">{t('todo.failed')}</p>
          {requestButton(t('todo.tryAgain'), 'todo-retry')}
        </TodoCard>
      )
    case 'completed': {
      const { tasks } = data.analysis
      if (tasks.length === 0) {
        return (
          <TodoCard title={t('todo.title')} testId="todo-empty">
            <p className="text-body-md">{t('todo.nothingToFix')}</p>
            <p className="text-body-sm text-ink-muted">{t('todo.notProof')}</p>
          </TodoCard>
        )
      }
      const findingsById = new Map(
        findings.map((finding) => [finding.finding_id, finding]),
      )
      const covered = new Set(tasks.flatMap((task) => task.finding_ids))
      const uncovered = findings.length - covered.size
      return (
        <TodoCard
          title={t('todo.title')}
          aside={t('todo.count', {
            tasks: tasks.length,
            fixed: covered.size,
            total: findings.length,
          })}
          testId="todo-list"
        >
          <p className="text-body-sm text-ink-muted">{t('todo.order')}</p>
          <ol>
            {tasks.map((task) => (
              <TaskRow
                key={task.rank}
                task={task}
                findingsById={findingsById}
                open={openRanks.has(task.rank)}
                onToggle={() =>
                  setOpenRanks((current) => {
                    const next = new Set(current)
                    if (next.has(task.rank)) next.delete(task.rank)
                    else next.add(task.rank)
                    return next
                  })
                }
              />
            ))}
          </ol>
          {uncovered > 0 && (
            <p className="text-body-sm text-ink-muted">
              {t('todo.uncovered', { count: uncovered })}
            </p>
          )}
          {data.analysis.not_checked && (
            <p className="text-body-sm text-ink-muted">
              {data.analysis.not_checked}
            </p>
          )}
          <p className="text-caption-md text-ink-muted">{t('todo.footer')}</p>
        </TodoCard>
      )
    }
  }
}

export default TodoList
