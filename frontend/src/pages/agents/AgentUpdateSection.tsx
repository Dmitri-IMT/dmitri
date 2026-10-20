import { useEffect, useState, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Dialog } from 'radix-ui'
import DialogShell from '@/components/DialogShell'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { useSession } from '@/auth/useSession'
import { queryKeys } from '@/api/queryKeys'
import type { AgentDetail } from '@/api/agents'
import type {
  AgentUpdateAvailability,
  UpdateOperationView,
} from '@/api/agentUpdates'
import { useAgentUpdate } from '@/hooks/useAgentUpdate'
import { useToast } from '@/hooks/useToast'
import useI18n from '@/i18n/useI18n'
import type { MessageKey } from '@/i18n/messages'

const phaseKeys: Record<UpdateOperationView['phase'], MessageKey> = {
  requested: 'updates.phase.requested',
  preparing: 'updates.phase.preparing',
  installing: 'updates.phase.installing',
  verifying: 'updates.phase.verifying',
  awaiting_confirmation: 'updates.phase.awaitingConfirmation',
  recovering: 'updates.phase.recovering',
  succeeded: 'updates.phase.succeeded',
  failed: 'updates.phase.failed',
  expired: 'updates.phase.expired',
  rolled_back: 'updates.phase.rolledBack',
  needs_intervention: 'updates.phase.intervention',
}

const availabilityKeys: Record<
  AgentUpdateAvailability['availability'],
  MessageKey
> = {
  available: 'updates.availability.available',
  up_to_date: 'updates.availability.upToDate',
  unknown: 'updates.availability.unknown',
  unavailable: 'updates.availability.unavailable',
}

const readinessKeys: Record<
  AgentUpdateAvailability['device_readiness'],
  MessageKey
> = {
  ready: 'updates.readiness.ready',
  offline: 'updates.readiness.offline',
  revoked: 'updates.readiness.revoked',
  bootstrap_required: 'updates.readiness.bootstrap',
  busy: 'updates.readiness.busy',
  unknown: 'updates.readiness.unknown',
}

const errorKeys: Record<
  NonNullable<UpdateOperationView['error_code']>,
  MessageKey
> = {
  device_busy: 'updates.error.deviceBusy',
  session_replaced: 'updates.error.sessionReplaced',
  request_expired: 'updates.error.requestExpired',
  release_not_allowed: 'updates.error.releaseNotAllowed',
  version_conflict: 'updates.error.versionConflict',
  metadata_untrusted: 'updates.error.metadataUntrusted',
  metadata_expired: 'updates.error.metadataExpired',
  artifact_mismatch: 'updates.error.artifactMismatch',
  unsupported_platform: 'updates.error.unsupportedPlatform',
  prerequisite_missing: 'updates.error.prerequisiteMissing',
  insufficient_resources: 'updates.error.insufficientResources',
  package_manager_busy: 'updates.error.packageManagerBusy',
  authorization_expired: 'updates.error.authorizationExpired',
  install_failed: 'updates.error.installFailed',
  local_health_failed: 'updates.error.localHealthFailed',
  recovery_failed: 'updates.error.recoveryFailed',
  state_corrupt: 'updates.error.stateCorrupt',
}

function formatDate(value: string | null, language: string) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return new Intl.DateTimeFormat(language, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function VersionRow({
  label,
  value,
  empty = '—',
}: {
  label: string
  value: string | null | undefined
  empty?: string
}) {
  return (
    <div className="flex flex-col gap-1 sm:flex-row sm:justify-between sm:gap-4">
      <dt className="text-body-sm text-muted-foreground">{label}</dt>
      <dd className="break-all text-body-md">{value || empty}</dd>
    </div>
  )
}

function OperationDetails({
  operation,
  language,
  t,
  live = false,
}: {
  operation: UpdateOperationView
  language: string
  t: (key: MessageKey, variables?: Record<string, string | number>) => string
  live?: boolean
}) {
  const phase = t(phaseKeys[operation.phase])
  const outcome = operation.local_outcome
    ? t(`updates.outcome.${operation.local_outcome}` as MessageKey)
    : t('updates.outcome.pending')
  return (
    <>
      {live && (
        <p role="status" aria-live="polite" className="sr-only">
          {phase}. {outcome}
        </p>
      )}
      <article
        className="flex flex-col gap-3 border-t border-border pt-4"
        data-testid={
          live ? 'agent-update-current' : 'agent-update-history-item'
        }
      >
        <p className="text-body-md font-medium">
          {operation.previous_version ?? t('updates.unknownValue')} →{' '}
          {operation.target_version} · {phase}
        </p>
        <dl className="flex flex-col gap-2">
          <VersionRow
            label={t('updates.packageVersion')}
            value={operation.observed_package_version}
            empty={t('updates.unknownValue')}
          />
          <VersionRow
            label={t('updates.localOutcome')}
            value={
              operation.local_outcome
                ? t(`updates.outcome.${operation.local_outcome}` as MessageKey)
                : t('updates.outcome.pending')
            }
          />
          <VersionRow
            label={t('updates.observedVersion')}
            value={operation.observed_version}
            empty={t('updates.unknownValue')}
          />
          <VersionRow
            label={t('updates.requestedBy')}
            value={operation.actor_display_snapshot}
          />
        </dl>
        <div className="flex flex-col gap-1 text-body-sm text-muted-foreground">
          <p>
            {t('updates.requestedAt', {
              date: formatDate(operation.requested_at, language) ?? '—',
            })}
          </p>
          {operation.local_completed_at && (
            <p>
              {t('updates.localCompletedAt', {
                date: formatDate(operation.local_completed_at, language) ?? '—',
              })}
            </p>
          )}
          {operation.confirmed_at && (
            <p>
              {t('updates.confirmedAt', {
                date: formatDate(operation.confirmed_at, language) ?? '—',
              })}
            </p>
          )}
          <p>
            {operation.last_contact_at
              ? t('updates.lastContactAt', {
                  date: formatDate(operation.last_contact_at, language) ?? '—',
                })
              : t('updates.contactUnknown')}
          </p>
        </div>
        {operation.phase === 'awaiting_confirmation' && (
          <p className="text-body-sm">
            {t('updates.awaitingRemoteConfirmation')}
          </p>
        )}
        {operation.phase === 'needs_intervention' && (
          <p className="text-body-sm">{t('updates.interventionNextStep')}</p>
        )}
        {operation.error_code && (
          <p className="text-body-sm">{t(errorKeys[operation.error_code])}</p>
        )}
      </article>
    </>
  )
}

function AgentUpdateSection({ agent }: { agent: AgentDetail }) {
  const { user } = useSession()
  const { t, language } = useI18n()
  const { show } = useToast()
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const confirmRef = useRef<HTMLButtonElement>(null)
  const notifiedFailures = useRef(new Map<string, boolean>())
  const updates = useAgentUpdate(agent.agent_id)
  const availability = updates.availability.data
  const release = availability?.release
  const installedVersion = agent.observed_version ?? null
  const canRequest =
    user?.role === 'admin' &&
    agent.revoked_at === null &&
    availability?.availability === 'available' &&
    availability.device_readiness === 'ready' &&
    Boolean(release && installedVersion)
  const currentOperation =
    updates.operation.data ?? updates.history.data?.data[0]
  const refreshing =
    updates.availability.isFetching || updates.history.isFetching

  useEffect(() => {
    const results = [
      {
        key: `availability:${agent.agent_id}`,
        query: updates.availability,
        message: 'updates.readFailed' as const,
      },
      {
        key: `history:${agent.agent_id}`,
        query: updates.history,
        message: 'updates.historyFailed' as const,
      },
      ...(updates.operation.isEnabled
        ? [
            {
              key: `operation:${currentOperation?.update_id ?? ''}`,
              query: updates.operation,
              message: 'updates.operationReadFailed' as const,
            },
          ]
        : []),
    ]
    for (const { key, query, message } of results) {
      if (query.isSuccess) notifiedFailures.current.delete(key)
      if (
        query.isError &&
        query.errorUpdateCount > 0 &&
        !notifiedFailures.current.has(key)
      ) {
        notifiedFailures.current.set(key, true)
        show(t(message))
      }
    }
  }, [
    agent.agent_id,
    currentOperation?.update_id,
    show,
    t,
    updates.availability,
    updates.history,
    updates.operation,
  ])

  async function refresh() {
    await updates.refresh()
  }

  async function confirmUpdate() {
    if (!release || !installedVersion || submitting) return
    setSubmitting(true)
    try {
      await updates.request(release.release_id, installedVersion)
      setDialogOpen(false)
      await queryClient.invalidateQueries({
        queryKey: queryKeys.agents.detail(agent.agent_id),
      })
    } catch {
      show(t('updates.requestFailed'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card data-testid="agent-update-section">
      <CardHeader>
        <h2 className="text-title-sm">{t('updates.title')}</h2>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <dl className="flex flex-col gap-3">
          <VersionRow
            label={t('updates.installedVersion')}
            value={installedVersion}
            empty={t('updates.unknownValue')}
          />
          <VersionRow
            label={t('updates.installedPackageVersion')}
            value={agent.observed_package_version}
            empty={t('updates.unknownValue')}
          />
          <VersionRow
            label={t('updates.versionObservedAt')}
            value={
              formatDate(agent.version_observed_at ?? null, language) ??
              t('updates.unknownValue')
            }
          />
          <VersionRow
            label={t('updates.availableVersion')}
            value={release?.upstream_version ?? null}
            empty={
              availability ? t('updates.unknownValue') : t('updates.loading')
            }
          />
          <VersionRow
            label={t('updates.availablePackageVersion')}
            value={release?.package_version ?? null}
            empty={
              availability ? t('updates.unknownValue') : t('updates.loading')
            }
          />
          {availability && (
            <VersionRow
              label={t('updates.availability')}
              value={t(availabilityKeys[availability.availability])}
            />
          )}
          {availability && (
            <VersionRow
              label={t('updates.readiness')}
              value={t(readinessKeys[availability.device_readiness])}
            />
          )}
          {availability && (
            <VersionRow
              label={t('updates.catalogueCheckedAt')}
              value={
                formatDate(availability.catalogue_checked_at, language) ??
                t('updates.unknownValue')
              }
            />
          )}
        </dl>

        {release && (
          <div className="flex flex-col gap-2">
            <h3 className="text-title-sm">{t('updates.releaseNotes')}</h3>
            <p className="max-w-prose whitespace-pre-wrap break-words text-body-md">
              {release.release_notes}
            </p>
          </div>
        )}
        {agent.revoked_at !== null && (
          <p className="text-body-sm">{t('updates.revokedReadOnly')}</p>
        )}
        {availability?.device_readiness === 'offline' && (
          <p className="text-body-sm">{t('updates.offlineNotQueued')}</p>
        )}
        <div className="flex flex-wrap gap-2">
          {canRequest && release && (
            <Button
              type="button"
              onClick={() => setDialogOpen(true)}
              data-testid="agent-update-trigger"
            >
              {t('updates.updateDevice')}
            </Button>
          )}
          <Button
            type="button"
            variant="outline"
            onClick={() => void refresh()}
            disabled={refreshing}
          >
            {refreshing ? t('updates.refreshing') : t('updates.refreshStatus')}
          </Button>
        </div>
        {currentOperation && (
          <OperationDetails
            operation={currentOperation}
            language={language}
            t={t}
            live
          />
        )}
        {updates.history.data?.data.length ? (
          <div
            className="flex flex-col gap-4"
            aria-label={t('updates.history')}
          >
            <h3 className="text-title-sm">{t('updates.history')}</h3>
            {updates.history.data.data.map((item) => (
              <OperationDetails
                key={item.update_id}
                operation={item}
                language={language}
                t={t}
              />
            ))}
          </div>
        ) : !updates.history.isLoading && !updates.history.isError ? (
          <p className="text-body-sm text-muted-foreground">
            {t('updates.noHistory')}
          </p>
        ) : null}
      </CardContent>

      <DialogShell
        open={dialogOpen}
        onOpenChange={(open) => {
          if (!submitting) setDialogOpen(open)
        }}
        testId="agent-update-dialog"
        locked={submitting}
        initialFocusRef={confirmRef}
      >
        <div className="flex flex-col gap-3">
          <Dialog.Title className="text-title-sm">
            {t('updates.confirmTitle')}
          </Dialog.Title>
          <Dialog.Description className="max-w-prose text-body-md text-muted-foreground">
            {t('updates.confirmDescription', {
              device: agent.display_name,
              version: release?.upstream_version ?? '',
            })}
          </Dialog.Description>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            {!submitting && (
              <Button
                className="w-full sm:w-auto"
                type="button"
                variant="outline"
                onClick={() => setDialogOpen(false)}
              >
                {t('updates.back')}
              </Button>
            )}
            <Button
              ref={confirmRef}
              className="w-full sm:w-auto"
              type="button"
              onClick={() => void confirmUpdate()}
              disabled={submitting}
              aria-label={t('updates.confirmAccessible', {
                version: release?.upstream_version ?? '',
              })}
            >
              {submitting ? t('updates.submitting') : t('updates.updateDevice')}
            </Button>
          </div>
        </div>
      </DialogShell>
    </Card>
  )
}

export default AgentUpdateSection
