import EmptyMark from '@/components/EmptyMark'
import type { components } from '@/types/openapi'

type Severity = components['schemas']['Severity']

const SEVERITY_LABEL: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

const SEVERITY_CLASS: Record<Severity, string> = {
  critical:
    'border-red-200 bg-red-100 text-red-800 dark:border-red-900 dark:bg-red-950/60 dark:text-red-200',
  high: 'border-orange-200 bg-orange-100 text-orange-800 dark:border-orange-900 dark:bg-orange-950/60 dark:text-orange-200',
  medium:
    'border-amber-200 bg-amber-100 text-amber-900 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-200',
  low: 'border-emerald-200 bg-emerald-100 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-200',
}

function SeverityWord({ severity }: { severity: Severity | null | undefined }) {
  if (severity == null) return <EmptyMark />
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-1 text-caption-md font-semibold ${SEVERITY_CLASS[severity]}`}
    >
      {SEVERITY_LABEL[severity]}
    </span>
  )
}

export default SeverityWord
