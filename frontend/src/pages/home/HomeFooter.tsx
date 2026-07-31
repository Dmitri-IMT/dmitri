import Timestamp from '@/components/Timestamp'
import type { components } from '@/types/openapi'

type ScanSummary = components['schemas']['ScanSummary']

function HomeFooter({ scan }: { scan: ScanSummary }) {
  return (
    <footer
      data-testid="home-footer"
      className="border-t border-rule pt-4 text-caption-md text-muted-foreground"
    >
      Last scan <Timestamp value={scan.timestamp} />
    </footer>
  )
}

export default HomeFooter
