import { useState } from 'react'
import { useNavigate } from 'react-router'
import { deleteHost } from '@/api/hosts'
import AdminOnly from '@/components/AdminOnly'
import ConfirmDialog from '@/components/ConfirmDialog'
import { Button } from '@/components/ui/button'
import { useRefreshAfterDelete } from '@/hooks/useRefreshAfterDelete'
import { useToast } from '@/hooks/useToast'
import useI18n from '@/i18n/useI18n'
import type { components } from '@/types/openapi'

type HostDetailResponse = components['schemas']['HostDetailResponse']

function HostDelete({ host }: { host: HostDetailResponse }) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { show } = useToast()
  const refresh = useRefreshAfterDelete()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const name = host.hostname || host.ip

  async function confirmDelete() {
    setError(null)
    try {
      await deleteHost(host.host_id)
    } catch {
      setError(t('deletion.deleteMachineError'))
      return
    }
    setDialogOpen(false)
    show(t('deletion.machineDeleted', { name }))
    void navigate('/network')
    void refresh()
  }

  return (
    <AdminOnly>
      <section data-testid="host-delete" className="flex flex-col gap-4">
        <h2 className="text-title-sm">{t('deletion.deleteMachineHeading')}</h2>
        <div>
          <Button
            type="button"
            variant="outline"
            onClick={() => setDialogOpen(true)}
            data-testid="host-delete-trigger"
          >
            {t('deletion.deleteMachine')}
          </Button>
        </div>
        <ConfirmDialog
          open={dialogOpen}
          onOpenChange={(open) => {
            setDialogOpen(open)
            if (!open) {
              setError(null)
            }
          }}
          title={t('deletion.deleteMachineQuestion', { name })}
          description={t('deletion.deleteMachineBody')}
          confirmLabel={t('deletion.deleteMachine')}
          pendingLabel={t('deletion.deleting')}
          onConfirm={confirmDelete}
          error={error}
          testId="host-delete"
        />
      </section>
    </AdminOnly>
  )
}

export default HostDelete
