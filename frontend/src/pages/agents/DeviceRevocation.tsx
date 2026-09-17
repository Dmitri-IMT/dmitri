import { useState } from 'react'
import { useSession } from '@/auth/useSession'
import AdminOnly from '@/components/AdminOnly'
import ConfirmDialog from '@/components/ConfirmDialog'
import { Button } from '@/components/ui/button'
import { useAgentRevocation } from '@/hooks/useAgentRevocation'
import type { components } from '@/types/openapi'

type AgentDetail = components['schemas']['AgentDetail']

function DeviceRevocation({
  agent,
  mode,
  onChanged,
}: {
  agent: AgentDetail
  mode: 'revoke' | 'restore'
  onChanged: () => void
}) {
  const { user } = useSession()
  const [dialogOpen, setDialogOpen] = useState(false)
  const { revoke, restore, restoring, revokeError, restoreError } =
    useAgentRevocation(agent)

  async function confirmRevoke() {
    if (await revoke()) {
      setDialogOpen(false)
      onChanged()
    }
  }

  async function confirmRestore() {
    if (await restore()) {
      onChanged()
    }
  }

  if (mode === 'restore') {
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
              onClick={() => void confirmRestore()}
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
              {restoreError}
            </p>
          </div>
        </AdminOnly>
      </section>
    )
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
          error={revokeError}
          testId="device-revoke"
        />
      </section>
    </AdminOnly>
  )
}

export default DeviceRevocation
