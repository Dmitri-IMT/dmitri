import { useState } from 'react'
import { useNavigate } from 'react-router'
import { readApiError } from '@/api/apiError'
import { deleteScan } from '@/api/scans'
import AdminOnly from '@/components/AdminOnly'
import ConfirmDialog from '@/components/ConfirmDialog'
import { Button } from '@/components/ui/button'
import { useRefreshAfterDelete } from '@/hooks/useRefreshAfterDelete'
import { useToast } from '@/hooks/useToast'
import useI18n from '@/i18n/useI18n'
import { isUnfinished } from '@/lib/scanStatus'
import type { components } from '@/types/openapi'

type ScanDetailResponse = components['schemas']['ScanDetailResponse']

function ScanDelete({ scan }: { scan: ScanDetailResponse }) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { show } = useToast()
  const refresh = useRefreshAfterDelete()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (isUnfinished(scan.status)) {
    return null
  }

  async function confirmDelete() {
    setError(null)
    try {
      await deleteScan(scan.scan_id)
    } catch (err) {
      const { status, code } = readApiError(err)
      setError(
        status === 409 && code === 'scan_running'
          ? t('deletion.scanRunningError')
          : t('deletion.deleteScanError'),
      )
      return
    }
    setDialogOpen(false)
    show(t('deletion.scanDeleted'))
    void navigate('/scans')
    void refresh()
  }

  return (
    <AdminOnly>
      <section data-testid="scan-delete" className="flex flex-col gap-4">
        <h2 className="text-title-sm">{t('deletion.deleteScanHeading')}</h2>
        <div>
          <Button
            type="button"
            variant="outline"
            onClick={() => setDialogOpen(true)}
            data-testid="scan-delete-trigger"
          >
            {t('deletion.deleteScan')}
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
          title={t('deletion.deleteScanQuestion')}
          description={t('deletion.deleteScanBody')}
          confirmLabel={t('deletion.deleteScan')}
          pendingLabel={t('deletion.deleting')}
          onConfirm={confirmDelete}
          error={error}
          testId="scan-delete"
        />
      </section>
    </AdminOnly>
  )
}

export default ScanDelete
