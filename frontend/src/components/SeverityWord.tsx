import EmptyMark from '@/components/EmptyMark'
import type { components } from '@/types/openapi'

type Severity = components['schemas']['Severity']

const SEVERITY_LABEL: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

function SeverityWord({ severity }: { severity: Severity | null | undefined }) {
  if (severity == null) return <EmptyMark />
  return <span className="font-semibold">{SEVERITY_LABEL[severity]}</span>
}

export default SeverityWord
