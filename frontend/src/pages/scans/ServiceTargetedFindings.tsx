import ScanDetailSection from '@/pages/scans/ScanDetailSection'
import FindingsTable from '@/pages/scans/FindingsTable'
import useI18n from '@/i18n/useI18n'
import { SEVERITY_ORDER } from '@/lib/severity'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']
type Severity = components['schemas']['Severity']

const SEVERITIES = Object.keys(SEVERITY_ORDER) as Severity[]

function ServiceTargetedFindings({
  findings,
  openFindingId,
  onOpenFindingChange,
}: {
  findings: FindingRecord[]
  openFindingId: string | null
  onOpenFindingChange: (id: string | null) => void
}) {
  const { t } = useI18n()
  const targeted = findings.filter(
    (finding) => finding.source === 'targeted_service_assessment',
  )
  const groups = SEVERITIES.map((severity) => ({
    severity,
    findings: targeted.filter((finding) => finding.severity === severity),
  })).filter((group) => group.findings.length > 0)

  if (targeted.length === 0) {
    return (
      <p className="text-body-md" data-testid="scan-no-targeted-findings">
        {t('scans.noTargetedFindings')}
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-4" data-testid="scan-targeted-findings">
      <p className="text-body-md text-muted-foreground">
        {t('scans.targetedFindingsDescription')}
      </p>
      {groups.map((group) => {
        const opensForDeepLink = group.findings.some(
          (finding) => finding.finding_id === openFindingId,
        )
        const testId = `targeted-${group.severity}`
        return (
          <ScanDetailSection
            key={group.severity}
            title={
              <span data-testid={`${testId}-heading`}>
                {t('common.severityGroupTitle', {
                  severity: group.severity,
                  count: group.findings.length,
                })}
              </span>
            }
            openToken={
              opensForDeepLink ? (openFindingId ?? undefined) : undefined
            }
            triggerAriaLabel={t('scans.targetedSeverityGroupToggle', {
              severity: t('common.severity', { severity: group.severity }),
            })}
          >
            <FindingsTable
              findings={group.findings}
              variant="scan"
              testId={testId}
              caption={t('scans.targetedFindingsCaption', {
                severity: t('common.severity', { severity: group.severity }),
              })}
              sourceToolLabel={t('scans.targetedToolLabel')}
              openFindingId={openFindingId}
              onOpenFindingChange={onOpenFindingChange}
            />
          </ScanDetailSection>
        )
      })}
    </div>
  )
}

export default ServiceTargetedFindings
