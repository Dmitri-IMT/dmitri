import { useState } from 'react'
import { readApiError } from '@/api/apiError'
import { useSession } from '@/auth/useSession'
import ConfirmByTyping from '@/components/ConfirmByTyping'
import Disclosure from '@/components/Disclosure'
import PageHeader from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import AccountDetails from '@/pages/settings/AccountDetails'
import PasswordDialog from '@/pages/settings/PasswordDialog'

const LAST_ADMIN_ERROR =
  "You're the only admin. Make someone else an admin first, then you can leave."
const LEAVE_ERROR = "Couldn't delete your account."

function Settings() {
  const { user, deleteAccount } = useSession()
  const [isPasswordOpen, setIsPasswordOpen] = useState(false)
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null)
  const [isLeaveOpen, setIsLeaveOpen] = useState(false)
  const [leaveError, setLeaveError] = useState<string | null>(null)

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
    <div data-testid="settings-idle" className="flex flex-col gap-12">
      <PageHeader title="Settings" />
      <div className="flex flex-col gap-12">
        <AccountDetails />
        <section className="flex flex-col gap-4">
          <h2 className="text-title-sm">Password</h2>
          <div className="flex flex-col items-start gap-2">
            <Button
              type="button"
              onClick={() => {
                setPasswordSuccess(null)
                setIsPasswordOpen(true)
              }}
              data-testid="settings-password-trigger"
            >
              Change password
            </Button>
            <p
              role="status"
              data-testid="settings-success"
              className="text-body-md text-muted-foreground"
            >
              {passwordSuccess}
            </p>
          </div>
        </section>
        <section
          data-testid="settings-activity"
          className="flex flex-col gap-2"
        >
          <h2 data-testid="settings-activity-label" className="text-title-sm">
            Activity
          </h2>
          <Disclosure
            label="What's recorded?"
            testId="settings-activity-disclosure"
            caretTestId="settings-activity-caret"
          >
            <p
              data-testid="settings-activity-note"
              className="max-w-prose text-body-md text-muted-foreground"
            >
              Everyone in your organization can see when you last signed in, and
              a log of changes to the organization: scans, machines that join
              the network, invitations, role changes, and members joining or
              leaving. We don&apos;t record what you viewed.
            </p>
          </Disclosure>
        </section>
        {user && (
          <section data-testid="settings-leave" className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <span className="text-title-sm">Leave this organisation</span>
              <p
                data-testid="settings-leave-body"
                className="max-w-prose text-body-md text-muted-foreground"
              >
                Your account is deleted and you lose access to this
                organisation&apos;s scans, network and vulnerabilities straight
                away. This can&apos;t be undone — an admin would have to invite
                you again.
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              className="self-start"
              onClick={() => setIsLeaveOpen(true)}
              data-testid="settings-leave-trigger"
            >
              Delete my account
            </Button>
          </section>
        )}
      </div>
      <PasswordDialog
        open={isPasswordOpen}
        onOpenChange={setIsPasswordOpen}
        onSuccess={() => setPasswordSuccess('Password changed.')}
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
          heading="Delete your account?"
          body="Your account is deleted and you lose access straight away. This can't be undone."
          expectedValue={user.email}
          confirmLabel="Delete my account"
          confirmPendingLabel="Deleting…"
          onConfirm={handleLeave}
          error={leaveError}
        />
      )}
    </div>
  )
}

export default Settings
