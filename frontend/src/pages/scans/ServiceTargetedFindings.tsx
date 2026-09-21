import FindingsTable from '@/pages/scans/FindingsTable'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']

const CATEGORIES = [
  { key: 'web', label: 'Web', tools: ['ffuf', 'nikto'] },
  { key: 'ssl', label: 'SSL / TLS', tools: ['testssl.sh'] },
  { key: 'smb', label: 'SMB', tools: ['enum4linux-ng'] },
  { key: 'ssh', label: 'SSH', tools: ['ssh-audit'] },
  { key: 'ftp', label: 'FTP', tools: ['ftp-check'] },
  { key: 'telnet', label: 'Telnet', tools: ['telnet-check'] },
] as const

export function targetedFindingsTableTestId(finding: FindingRecord): string {
  const category = CATEGORIES.find((item) =>
    item.tools.some((tool) => tool === finding.source_script),
  )
  return `targeted-${category?.key ?? 'other'}`
}

function ServiceTargetedFindings({
  findings,
  openFindingId,
  onOpenFindingChange,
}: {
  findings: FindingRecord[]
  openFindingId: string | null
  onOpenFindingChange: (id: string | null) => void
}) {
  const targeted = findings.filter(
    (finding) => finding.source === 'targeted_service_assessment',
  )
  const groups = CATEGORIES.map((category) => ({
    ...category,
    findings: targeted.filter((finding) =>
      category.tools.some((tool) => tool === finding.source_script),
    ),
  })).filter((group) => group.findings.length > 0)
  const other = targeted.filter(
    (finding) =>
      !CATEGORIES.some((category) =>
        category.tools.some((tool) => tool === finding.source_script),
      ),
  )

  if (targeted.length === 0) {
    return (
      <p className="text-body-md" data-testid="scan-no-targeted-findings">
        No service-targeted findings were reported in this scan. This does not
        mean every tool ran.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-8" data-testid="scan-targeted-findings">
      {[
        ...groups,
        ...(other.length > 0
          ? [{ key: 'other', label: 'Other services', findings: other }]
          : []),
      ].map((group) => (
        <section key={group.key} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <h3 className="text-title-xs">{group.label}</h3>
            <p className="text-body-sm text-muted-foreground">
              {Array.from(
                new Set(group.findings.map((finding) => finding.source_script)),
              )
                .filter((source): source is string => source != null)
                .join(', ')}
            </p>
          </div>
          <FindingsTable
            findings={group.findings}
            variant="scan"
            testId={`targeted-${group.key}`}
            caption={`${group.label} service-targeted findings in this scan`}
            openFindingId={openFindingId}
            onOpenFindingChange={onOpenFindingChange}
          />
        </section>
      ))}
    </div>
  )
}

export default ServiceTargetedFindings
