import { useEffect, useRef, useState } from 'react'
import { useSession } from '@/auth/useSession'
import { useScanCommand } from '@/hooks/useScanCommand'
import AgentIdentity from './AgentIdentity'
import ScanControl from './ScanControl'
import TargetSubnetSection from './TargetSubnetSection'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']

function AgentCard({ agent }: { agent: AgentDetail }) {
  const { user } = useSession()
  const [chooserOpen, setChooserOpen] = useState(
    user?.role === 'admin' && agent.target_subnet == null,
  )
  const [focusRequest, setFocusRequest] = useState(0)
  const scanCommand = useScanCommand(agent, () => setChooserOpen(true))
  const cardRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (focusRequest === 0) return
    cardRef.current
      ?.querySelector<HTMLElement>('[data-testid="agents-scan-now"]')
      ?.focus()
  }, [agent.target_subnet, focusRequest])

  return (
    <div
      ref={cardRef}
      data-testid="agents-card"
      className="flex flex-col gap-6 border border-border bg-card p-6"
    >
      <AgentIdentity agent={agent} />
      <TargetSubnetSection
        agent={agent}
        open={chooserOpen}
        onOpenChange={setChooserOpen}
        onSaved={() => setFocusRequest((request) => request + 1)}
      />
      {!chooserOpen && (
        <ScanControl
          scanCommand={scanCommand}
          hasTarget={agent.target_subnet != null}
        />
      )}
    </div>
  )
}

export default AgentCard
