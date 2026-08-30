import EmptyMark from '@/components/EmptyMark'
import Timestamp from '@/components/Timestamp'
import type { components } from '@/types/openapi'

type ScanSummary = components['schemas']['ScanSummary']
type AgentDetail = components['schemas']['AgentDetail']

function HomeFooter({
  scan,
  agent,
  variant,
}: {
  scan?: ScanSummary
  agent: AgentDetail | null
  variant: 'clear' | 'pending'
}) {
  const showScanLine = variant === 'clear' && scan
  const showPiLine = agent !== null

  if (!showScanLine && !showPiLine) return null

  return (
    <footer
      data-testid="home-footer"
      className="flex flex-col gap-2 border-t border-rule pt-4 text-caption-md text-muted-foreground"
    >
      {showScanLine && (
        <p data-testid="home-footer-scan">
          Last scan: <Timestamp value={scan.timestamp} /> · {scan.host_count}{' '}
          hosts · {scan.scan_mode} mode
        </p>
      )}
      {showPiLine && (
        <p data-testid="home-footer-pi">
          Pi status: {agent.online ? 'online' : 'offline'} · last seen{' '}
          {agent.last_seen_at ? (
            <Timestamp value={agent.last_seen_at} />
          ) : (
            <EmptyMark />
          )}
        </p>
      )}
    </footer>
  )
}

export default HomeFooter
