import { useState } from 'react'
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
  const [savedTargetSubnet, setSavedTargetSubnet] = useState(false)
  const scanCommand = useScanCommand(agent)

  return (
    <div
      data-testid="agents-card"
      className="flex flex-col gap-6 border border-border bg-card p-6"
    >
      <AgentIdentity agent={agent} />
      <TargetSubnetSection
        agent={agent}
        open={chooserOpen}
        onOpenChange={setChooserOpen}
        onSaved={() => setSavedTargetSubnet(true)}
      />
      {!chooserOpen && (
        <ScanControl
          scanCommand={scanCommand}
          hasTarget={agent.target_subnet != null}
          autoFocus={savedTargetSubnet}
          onSubnetStale={() => {
            setSavedTargetSubnet(false)
            setChooserOpen(true)
          }}
        />
      )}
    </div>
  )
}

export default AgentCard
