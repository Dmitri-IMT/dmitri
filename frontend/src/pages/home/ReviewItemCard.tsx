import SeverityBadge from '@/components/SeverityBadge'
import Timestamp from '@/components/Timestamp'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']

type ReviewItemCardProps =
  | { variant: 'finding'; finding: FindingRecord }
  | { variant: 'scan' }
  | { variant: 'coverage'; days: number }

const LABEL: Record<ReviewItemCardProps['variant'], string> = {
  finding: 'FINDING',
  scan: 'SCAN',
  coverage: 'COVERAGE',
}

function ReviewItemCard(props: ReviewItemCardProps) {
  const testId =
    props.variant === 'scan'
      ? 'home-item-scan'
      : props.variant === 'coverage'
        ? 'home-item-coverage'
        : undefined

  return (
    <div
      data-testid={testId}
      className="flex flex-col gap-3 border border-rule bg-card p-6"
    >
      <div className="flex items-start justify-between gap-4">
        <span className="text-caption-md font-medium tracking-widest text-accent">
          {LABEL[props.variant]}
        </span>
        {props.variant === 'finding' && (
          <span data-testid="home-item-severity">
            <SeverityBadge severity={props.finding.severity} />
          </span>
        )}
      </div>
      {props.variant === 'finding' && (
        <p className="text-body-md">
          {props.finding.cve_id ?? props.finding.title} on{' '}
          {props.finding.host_ip ?? 'an unknown host'}. Found in{' '}
          <Timestamp value={props.finding.detected_at} /> scan.
        </p>
      )}
      {props.variant === 'scan' && (
        <p className="text-body-md">
          Last night&apos;s scan didn&apos;t finish.
        </p>
      )}
      {props.variant === 'coverage' && (
        <p className="text-body-md">No successful scan in {props.days} days.</p>
      )}
    </div>
  )
}

export default ReviewItemCard
