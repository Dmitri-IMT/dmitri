import AdminOnly from '@/components/AdminOnly'
import { Button } from '@/components/ui/button'
import { useUpdateTargetSubnet } from '@/hooks/useUpdateTargetSubnet'
import { useSession } from '@/auth/useSession'
import {
  resolveWatchedNetwork,
  watchedNetworkLabel,
} from '@/pages/agents/watchedNetworkLabel'
import SubnetChooser from './SubnetChooser'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']

type Props = {
  agent: AgentDetail
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}

type ChooserSessionProps = {
  agent: AgentDetail
  onSaved: () => void
}

function ChooserSession({ agent, onSaved }: ChooserSessionProps) {
  const { selected, saving, refusal, selectSubnet, save } =
    useUpdateTargetSubnet(agent, onSaved)

  return (
    <SubnetChooser
      subnets={agent.available_subnets}
      selected={selected}
      saving={saving}
      refusal={refusal}
      onSelected={selectSubnet}
      onSubmit={() => void save()}
    />
  )
}

function TargetSubnetSection({ agent, open, onOpenChange, onSaved }: Props) {
  const { user } = useSession()
  const target = resolveWatchedNetwork(agent)

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-title-sm">Watched network</h3>
      {!open && (
        <div className="flex items-center justify-between gap-6">
          <p
            data-testid="agents-network"
            className="min-w-0 text-body-md text-muted-foreground"
          >
            {agent.target_subnet
              ? watchedNetworkLabel(agent.target_subnet, target)
              : user?.role === 'viewer'
                ? 'No network chosen yet. Ask your admin to choose one.'
                : 'No network chosen yet.'}
          </p>
          {agent.target_subnet && (
            <AdminOnly>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(true)}
                data-testid="agents-network-change"
              >
                Change
              </Button>
            </AdminOnly>
          )}
        </div>
      )}
      {open && (
        <AdminOnly>
          <ChooserSession
            agent={agent}
            onSaved={() => {
              onOpenChange(false)
              onSaved()
            }}
          />
        </AdminOnly>
      )}
    </div>
  )
}

export default TargetSubnetSection
