import { useState } from 'react'
import { readApiError } from '@/api/apiError'
import { useSession } from '@/auth/useSession'
import ConfirmByTyping from '@/components/ConfirmByTyping'
import Disclosure from '@/components/Disclosure'
import PageHeader from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import PasswordDialog from '@/pages/settings/PasswordDialog'
import AIUsagePanel from '@/pages/settings/AIUsagePanel'
import DeleteDataPanel from '@/pages/settings/DeleteDataPanel'
import useI18n from '@/i18n/useI18n'

const LAST_ADMIN_ERROR =
  "You're the only admin. Make someone else an admin first, then you can leave."
const LEAVE_ERROR = "Couldn't delete your account."

function ValuePlaceholder() {
  return <span className="block h-3 w-32 bg-border" />
}

function Settings() {
  const { user, deleteAccount } = useSession()
  const { t } = useI18n()
  const [isPasswordOpen, setIsPasswordOpen] = useState(false)
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null)
  const [isLeaveOpen, setIsLeaveOpen] = useState(false)
  const [leaveError, setLeaveError] = useState<string | null>(null)

  const roleLabel = user
    ? user.role === 'admin'
      ? t('settings.admin')
      : t('settings.viewer')
    : null

  async function handleLeave() {
    setLeaveError(null)
    try {
      await deleteAccount()
    } catch (err) {
      const { status, code } = readApiError(err)
      setLeaveError(
        status === 409 && code === 'last_admin'
          ? LAST_ADMIN_ERROR
          : LEAVE_ERROR,
      )
    }
  }

  return (
    <div data-testid="settings-idle" className="flex flex-col gap-8">
      <PageHeader title={t('nav.settings')} />
      <section data-testid="settings-details" className="flex flex-col gap-4">
        <h2 className="text-title-sm">{t('settings.account')}</h2>
        <dl className="flex flex-col gap-2 text-body-md">
          <div className="flex min-w-0 gap-2">
            <dt className="shrink-0 text-muted-foreground">
              {t('settings.email')}
            </dt>
            <dd
              data-testid="settings-details-email"
              className="min-w-0 break-words"
            >
              {user ? user.email : <ValuePlaceholder />}
            </dd>
          </div>
          <div className="flex min-w-0 gap-2">
            <dt className="shrink-0 text-muted-foreground">
              {t('settings.role')}
            </dt>
            <dd data-testid="settings-details-role" className="min-w-0">
              {roleLabel ?? <ValuePlaceholder />}
            </dd>
          </div>
        </dl>
        <div className="flex flex-col items-start gap-2">
          <Button
            type="button"
            onClick={() => {
              setPasswordSuccess(null)
              setIsPasswordOpen(true)
            }}
            data-testid="settings-password-trigger"
          >
            {t('settings.changePassword')}
          </Button>
          <p
            role="status"
            data-testid="settings-success"
            className="text-body-md text-muted-foreground"
          >
            {passwordSuccess}
          </p>
        </div>
        <div data-testid="settings-activity">
          <Disclosure
            label={t('settings.recordedAbout')}
            testId="settings-activity-disclosure"
            caretTestId="settings-activity-caret"
          >
            <p
              data-testid="settings-activity-note"
              className="max-w-prose text-body-md text-muted-foreground"
            >
              {t('settings.activityDescription')}
            </p>
          </Disclosure>
        </div>
      </section>
      <AIUsagePanel />
      <hr className="border-border" />
      <DeleteDataPanel />
      <section data-testid="settings-leave" className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <h2 className="text-title-sm">{t('settings.leaveOrganisation')}</h2>
          <p
            data-testid="settings-leave-body"
            className="max-w-prose text-body-md text-muted-foreground"
          >
            {t('settings.leaveDescription')}
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          className="self-start"
          disabled={!user}
          onClick={() => setIsLeaveOpen(true)}
          data-testid="settings-leave-trigger"
        >
          {t('settings.deleteAccount')}
        </Button>
      </section>
      <PasswordDialog
        open={isPasswordOpen}
        onOpenChange={setIsPasswordOpen}
        onSuccess={() => setPasswordSuccess(t('settings.passwordChanged'))}
      />
      {user && (
        <ConfirmByTyping
          open={isLeaveOpen}
          onOpenChange={(open) => {
            setIsLeaveOpen(open)
            if (!open) {
              setLeaveError(null)
            }
          }}
          heading={t('settings.deleteAccountQuestion')}
          body={t('settings.deleteAccountBody')}
          expectedValue={user.email}
          confirmLabel={t('settings.deleteAccount')}
          confirmPendingLabel="Deleting…"
          onConfirm={handleLeave}
          error={leaveError}
        />
      )}
    </div>
  )
}

export default Settings
