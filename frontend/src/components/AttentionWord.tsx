import type { components } from '@/types/openapi'

type ExposureAttention = components['schemas']['ExposureAttention']

const ATTENTION_LABEL: Record<ExposureAttention, string> = {
  informational: 'For awareness',
  review: 'Needs review',
  priority: 'Priority review',
}

function AttentionWord({ attention }: { attention: ExposureAttention }) {
  return <span>{ATTENTION_LABEL[attention]}</span>
}

export default AttentionWord
