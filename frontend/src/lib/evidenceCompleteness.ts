import type { MessageKey } from '@/i18n/messages'
import type { components } from '@/types/openapi'

type EvidenceCompleteness = components['schemas']['EvidenceCompleteness']

export function evidenceLimitKey(
  completeness: EvidenceCompleteness,
): MessageKey | null {
  if (completeness === 'partial') {
    return 'ai.partialLimit'
  }
  if (completeness === 'unknown') {
    return 'ai.unknownLimit'
  }
  return null
}
