import { useState } from 'react'
import { useParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { useSession } from '@/auth/useSession'
import { getAgent } from '@/api/agents'
import { queryKeys } from '@/api/queryKeys'
import BackLink from '@/components/BackLink'
import ReadDetailGate from '@/components/ReadDetailGate'
import { useScanCommand } from '@/hooks/useScanCommand'
import { DEFAULT_SCAN_MODE } from '@/lib/scanModes'
import { readDetailState } from '@/lib/detailState'
import AgentIdentity from '@/pages/agents/AgentIdentity'
import ScanControl from '@/pages/agents/ScanControl'
import ScanTypeTabs, { ScanTypeReadOnly } from '@/pages/agents/ScanTypeTabs'
import TargetSubnetSection from '@/pages/agents/TargetSubnetSection'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']
type ScanMode = components['schemas']['ScanMode']

function DeviceDetailBody({ agent }: { agent: AgentDetail }) {
  const { user } = useSession()
  const [savedTargetSubnet, setSavedTargetSubnet] = useState(false)
  const [selectedMode, setSelectedMode] = useState<ScanMode>(DEFAULT_SCAN_MODE)
  const scanCommand = useScanCommand(agent)
  const isAdmin = user?.role === 'admin'
  const needsNetworkChoice = isAdmin && agent.target_subnet == null
  const [chooserEditing, setChooserEditing] = useState(false)
  const chooserOpen = needsNetworkChoice || chooserEditing

  const showScanSection =
    !chooserOpen && (agent.target_subnet != null || scanCommand.following)

  return (
    <div className="flex flex-col gap-12">
      <BackLink fallback="/devices" testId="device-detail-back" />
      <AgentIdentity agent={agent} />
      <TargetSubnetSection
        agent={agent}
        open={chooserOpen}
        onOpenChange={setChooserEditing}
        onSaved={() => setSavedTargetSubnet(true)}
      />
      {showScanSection && (
        <div className="flex flex-col gap-4">
          {agent.target_subnet != null &&
            (isAdmin ? (
              <ScanTypeTabs value={selectedMode} onChange={setSelectedMode} />
            ) : (
              <ScanTypeReadOnly />
            ))}
          <ScanControl
            agent={agent}
            scanCommand={scanCommand}
            selectedMode={selectedMode}
            hasTarget={agent.target_subnet != null}
            autoFocus={savedTargetSubnet}
            onSubnetStale={() => {
              setSavedTargetSubnet(false)
              setChooserEditing(true)
            }}
          />
        </div>
      )}
    </div>
  )
}

function DeviceDetail() {
  const { agentId = '' } = useParams()

  const query = useQuery({
    queryKey: queryKeys.agents.detail(agentId),
    queryFn: () => getAgent(agentId),
    enabled: agentId !== '',
  })

  return (
    <ReadDetailGate
      testId="device-detail"
      title="Device"
      notFoundMessage="That device doesn't exist."
      errorMessage="Couldn't load this device."
      backTo="/devices"
      backLabel="Back to devices"
      detail={readDetailState(agentId, query)}
    >
      {(agent) => <DeviceDetailBody agent={agent} />}
    </ReadDetailGate>
  )
}

export default DeviceDetail
