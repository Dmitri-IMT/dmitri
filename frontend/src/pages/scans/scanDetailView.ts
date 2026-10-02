import { isUnfinished } from '@/lib/scanStatus'
import type { components } from '@/types/openapi'

type ScanDetailResponse = components['schemas']['ScanDetailResponse']
type FindingRecord = components['schemas']['FindingRecord']

const TARGETED_SOURCE = 'targeted_service_assessment'

export function isTargetedFinding(finding: FindingRecord): boolean {
  return finding.source === TARGETED_SOURCE
}

export type ScanDetailBody = 'stopped' | 'progress' | 'evidence' | 'none'

export interface ScanDetailView {
  body: ScanDetailBody
  failed: boolean
  partial: boolean
  stoppedEarly: boolean
  sections: {
    aiAnalysis: boolean
    noFindings: boolean
    attackSurface: boolean
    targeted: boolean
    coverage: boolean
    industrial: boolean
    machines: boolean
  }
}

export function scanDetailView(scan: ScanDetailResponse): ScanDetailView {
  const metadata = scan.metadata ?? {}
  const coverage = scan.coverage ?? []
  const failed = scan.status === 'failed'
  const hasRecordedEvidence =
    scan.findings.length > 0 ||
    scan.exposures.length > 0 ||
    scan.hosts.length > 0 ||
    coverage.length > 0
  const body: ScanDetailBody =
    scan.status === 'cancelled'
      ? 'stopped'
      : isUnfinished(scan.status)
        ? 'progress'
        : !failed || hasRecordedEvidence
          ? 'evidence'
          : 'none'
  const showsEmptyStates = !failed

  return {
    body,
    failed,
    partial: metadata.partial_result === true,
    stoppedEarly: scan.terminated_by === 'user_cancel',
    sections: {
      aiAnalysis: !failed,
      noFindings:
        showsEmptyStates &&
        !scan.findings.some((finding) => !isTargetedFinding(finding)),
      attackSurface: showsEmptyStates || scan.exposures.length > 0,
      targeted:
        metadata.targeted_units_planned != null ||
        scan.findings.some(isTargetedFinding),
      coverage: showsEmptyStates || coverage.length > 0,
      industrial: scan.hosts.some(
        (host) => host.industrial_services.length > 0,
      ),
      machines: showsEmptyStates || scan.hosts.length > 0,
    },
  }
}
