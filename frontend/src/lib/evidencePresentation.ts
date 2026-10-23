import type useI18n from '@/i18n/useI18n'
import type { components } from '@/types/openapi'
type Translate = ReturnType<typeof useI18n>['t']
type FindingRecord = components['schemas']['FindingRecord']
type EvidenceSummary = components['schemas']['FindingEvidenceSummary']
type EvidenceObservation =
  components['schemas']['FindingEvidenceObservationPayload']

export function methodLabel(
  method: EvidenceObservation['method'],
  t: Translate,
) {
  switch (method) {
    case 'version_correlation':
      return t('evidence.method.version_correlation')
    case 'configuration_observation':
      return t('evidence.method.configuration_observation')
    case 'specific_check':
      return t('evidence.method.specific_check')
    case 'textual_reference':
      return t('evidence.method.textual_reference')
    case 'unknown':
      return t('evidence.method.unknown')
  }
}

export function confidenceLabel(
  confidence: keyof EvidenceSummary['by_confidence'],
  t: Translate,
) {
  switch (confidence) {
    case 'tentative':
      return t('evidence.confidence.tentative')
    case 'probable':
      return t('evidence.confidence.probable')
    case 'confirmed':
      return t('evidence.confidence.confirmed')
    case 'unknown':
      return t('evidence.confidence.unknown')
  }
}

export function statusLabel(
  status: FindingRecord['evidence_status'],
  method: FindingRecord['detection_method'],
  t: Translate,
) {
  switch (status) {
    case 'supported':
      if (method === 'version_correlation') {
        return t('evidence.status.supportedVersionCorrelation')
      }
      return t('evidence.status.supported')
    case 'inconclusive':
      return t('evidence.status.inconclusive')
    case 'conflicting':
      return t('evidence.status.conflicting')
    case 'unknown':
      return t('evidence.status.unknown')
  }
}

export function evidenceExplanation(
  finding: FindingRecord,
  t: Translate,
): string {
  if (finding.evidence_status === 'conflicting')
    return t('evidence.explanation.conflicting')
  if (finding.evidence_status === 'inconclusive')
    return t('evidence.explanation.inconclusive')
  if (
    finding.evidence_status === 'unknown' &&
    (finding.evidence_observations ?? []).length === 0
  ) {
    return t('evidence.explanation.legacy')
  }
  if (finding.detection_method === 'version_correlation')
    return t('evidence.explanation.correlation')
  if (finding.detection_method === 'configuration_observation')
    return t('evidence.explanation.configuration')
  if (finding.detection_method === 'specific_check')
    return t('evidence.explanation.specificCheck')
  if (finding.detection_method === 'textual_reference')
    return t('evidence.explanation.textReference')
  return t('evidence.explanation.unknown')
}
