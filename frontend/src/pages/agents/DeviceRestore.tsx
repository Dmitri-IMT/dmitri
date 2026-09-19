import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { restoreAgent } from '@/api/agents'
import { queryKeys } from '@/api/queryKeys'
import { useSession } from '@/auth/useSession'
import AdminOnly from '@/components/AdminOnly'
import { Button } from '@/components/ui/button'
import { useToast } from '@/hooks/useToast'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']

function DeviceRestore({
  agent,
  onRestored,
}: {
  agent: AgentDetail
  onRestored: () => void
}) {
  const { user } = useSession()
  const queryClient = useQueryClient()
  const { show } = useToast()
  const [restoring, setRestoring] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function restore() {
    setError(null)
    setRestoring(true)
    try {
      await restoreAgent(agent.agent_id)
      await queryClient.invalidateQueries({ queryKey: queryKeys.agents.all })
    } catch {
      setError("Couldn't restore this device. Try again.")
      return
    } finally {
      setRestoring(false)
    }
    show(
      `${agent.display_name} was restored. It reconnects on its next hourly attempt, within the hour.`,
    )
    onRestored()
  }

  return (
    <section data-testid="device-revoked" className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <h3 className="text-title-sm">This device is revoked</h3>
        <p
          data-testid="device-revoked-body"
          className="max-w-prose text-body-md text-muted-foreground"
        >
          {user?.role === 'admin'
            ? "It can't connect, scan or send results. Once restored, it reconnects on its next hourly attempt, within the hour."
            : "It can't connect, scan or send results. Ask your admin to restore it."}
        </p>
      </div>
      <AdminOnly>
        <div className="flex flex-col items-start gap-2">
          <Button
            type="button"
            onClick={() => void restore()}
            disabled={restoring}
            data-testid="device-restore"
          >
            {restoring ? 'Restoring…' : 'Restore device'}
          </Button>
          <p
            role="alert"
            data-testid="device-restore-error"
            className="text-body-sm text-ink"
          >
            {error}
          </p>
        </div>
      </AdminOnly>
    </section>
  )
}

export default DeviceRestore
