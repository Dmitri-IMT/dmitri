import { useState } from 'react'
import { deleteAllHosts } from '@/api/hosts'
import { deleteAllScans } from '@/api/scans'
import { useSession } from '@/auth/useSession'
import AdminOnly from '@/components/AdminOnly'
import ConfirmByTyping from '@/components/ConfirmByTyping'
import { Button } from '@/components/ui/button'
import { useRefreshAfterDelete } from '@/hooks/useRefreshAfterDelete'
import { useToast } from '@/hooks/useToast'
import useI18n from '@/i18n/useI18n'

type Target = 'scans' | 'machines'

function DeleteDataPanel() {
  const { user } = useSession()
  const { t } = useI18n()
  const { show } = useToast()
  const refresh = useRefreshAfterDelete()
  const [target, setTarget] = useState<Target | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function deleteScans() {
    const result = await deleteAllScans()
    show(
      result.skipped > 0
        ? `${t('deletion.scansDeleted', { count: result.deleted })} ${t('deletion.scansSkipped', { count: result.skipped })}`
        : t('deletion.scansDeleted', { count: result.deleted }),
    )
  }

  async function deleteMachines() {
    const result = await deleteAllHosts()
    show(t('deletion.machinesDeleted', { count: result.deleted }))
  }

  async function handleConfirm() {
    setError(null)
    try {
      await (target === 'scans' ? deleteScans() : deleteMachines())
    } catch {
      setError(
        target === 'scans'
          ? t('deletion.deleteAllScansError')
          : t('deletion.deleteAllMachinesError'),
      )
      return
    }
    setTarget(null)
    void refresh()
  }

  return (
    <AdminOnly>
      <section
        data-testid="settings-delete-data"
        className="flex flex-col gap-4"
      >
        <h2 className="text-title-sm">{t('deletion.deleteData')}</h2>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            disabled={!user}
            onClick={() => setTarget('scans')}
            data-testid="settings-delete-scans-trigger"
          >
            {t('deletion.deleteAllScans')}
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={!user}
            onClick={() => setTarget('machines')}
            data-testid="settings-delete-machines-trigger"
          >
            {t('deletion.deleteAllMachines')}
          </Button>
        </div>
        {user && (
          <ConfirmByTyping
            open={target !== null}
            onOpenChange={(open) => {
              if (!open) {
                setTarget(null)
                setError(null)
              }
            }}
            heading={
              target === 'machines'
                ? t('deletion.deleteAllMachinesQuestion')
                : t('deletion.deleteAllScansQuestion')
            }
            body={
              target === 'machines'
                ? t('deletion.deleteAllMachinesBody')
                : t('deletion.deleteAllScansBody')
            }
            expectedValue={user.org_name}
            confirmLabel={
              target === 'machines'
                ? t('deletion.deleteAllMachines')
                : t('deletion.deleteAllScans')
            }
            confirmPendingLabel={t('deletion.deleting')}
            onConfirm={handleConfirm}
            error={error}
          />
        )}
      </section>
    </AdminOnly>
  )
}

export default DeleteDataPanel
