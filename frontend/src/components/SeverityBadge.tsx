import { cn } from '@/lib/utils'
import type { components } from '@/types/openapi'

type Severity = components['schemas']['Severity']

const SEVERITY_LABEL: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

const SEVERITY_CLASS: Record<Severity, string> = {
  critical: 'border-sev-critical bg-sev-critical/10 text-sev-critical',
  high: 'border-sev-high bg-sev-high/10 text-sev-high',
  medium: 'border-sev-medium bg-sev-medium/10 text-sev-medium',
  low: 'border-sev-low bg-sev-low/10 text-sev-low',
}

function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 border px-2 py-1 text-caption-md',
        SEVERITY_CLASS[severity],
      )}
    >
      {SEVERITY_LABEL[severity]}
    </span>
  )
}

export default SeverityBadge
