import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { revokeAgent } from '@/api/agents'
import { queryKeys } from '@/api/queryKeys'
import AdminOnly from '@/components/AdminOnly'
import ConfirmDialog from '@/components/ConfirmDialog'
import { Button } from '@/components/ui/button'
import { useToast } from '@/hooks/useToast'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']

function DeviceRevoke({
  agent,
  onRevoked,
}: {
  agent: AgentDetail
  onRevoked: () => void
}) {
  const queryClient = useQueryClient()
  const { show } = useToast()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function confirmRevoke() {
    setError(null)
    try {
      await revokeAgent(agent.agent_id)
      await queryClient.invalidateQueries({ queryKey: queryKeys.agents.all })
    } catch {
      setError("Couldn't revoke this device. Try again.")
      return
    }
    show(`${agent.display_name} was revoked.`)
    setDialogOpen(false)
    onRevoked()
  }

  return (
    <AdminOnly>
      <section data-testid="device-revoke" className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <h3 className="text-title-sm">Revoke this device</h3>
          <p className="max-w-prose text-body-md text-muted-foreground">
            It disconnects straight away and can't scan or send results until an
            admin restores it.
          </p>
        </div>
        <div>
          <Button
            type="button"
            variant="outline"
            onClick={() => setDialogOpen(true)}
            data-testid="device-revoke-trigger"
          >
            Revoke device
          </Button>
        </div>
        <ConfirmDialog
          open={dialogOpen}
          onOpenChange={setDialogOpen}
          title={`Revoke ${agent.display_name}?`}
          description="It disconnects straight away and can't scan or send results. You can restore it later; it reconnects within an hour of being restored."
          confirmLabel="Revoke device"
          pendingLabel="Revoking…"
          onConfirm={confirmRevoke}
          error={error}
          testId="device-revoke"
        />
      </section>
    </AdminOnly>
  )
}

export default DeviceRevoke
