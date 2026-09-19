import { useState } from 'react'
import { readApiError } from '@/api/apiError'
import { useSession } from '@/auth/useSession'
import ConfirmByTyping from '@/components/ConfirmByTyping'
import Disclosure from '@/components/Disclosure'
import PageHeader from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import PasswordDialog from '@/pages/settings/PasswordDialog'
import AIUsagePanel from '@/pages/settings/AIUsagePanel'

const LAST_ADMIN_ERROR =
  "You're the only admin. Make someone else an admin first, then you can leave."
const LEAVE_ERROR = "Couldn't delete your account."

function ValuePlaceholder() {
  return <span className="block h-3 w-32 bg-border" />
}

function Settings() {
  const { user, deleteAccount } = useSession()
  const [isPasswordOpen, setIsPasswordOpen] = useState(false)
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null)
  const [isLeaveOpen, setIsLeaveOpen] = useState(false)
  const [leaveError, setLeaveError] = useState<string | null>(null)

  const roleLabel = user ? (user.role === 'admin' ? 'Admin' : 'Viewer') : null

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
      <PageHeader title="Settings" />
      <section data-testid="settings-details" className="flex flex-col gap-4">
        <h2 className="text-title-sm">Your account</h2>
        <dl className="flex flex-col gap-2 text-body-md">
          <div className="flex min-w-0 gap-2">
            <dt className="shrink-0 text-muted-foreground">Email</dt>
            <dd
              data-testid="settings-details-email"
              className="min-w-0 break-words"
            >
              {user ? user.email : <ValuePlaceholder />}
            </dd>
          </div>
          <div className="flex min-w-0 gap-2">
            <dt className="shrink-0 text-muted-foreground">Role</dt>
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
        <div data-testid="settings-activity">
          <Disclosure
            label="What's recorded about me?"
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
        </div>
      </section>
      <AIUsagePanel />
      <hr className="border-border" />
      <section data-testid="settings-leave" className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <h2 className="text-title-sm">Leave this organisation</h2>
          <p
            data-testid="settings-leave-body"
            className="max-w-prose text-body-md text-muted-foreground"
          >
            Your account is deleted and you lose access to this
            organisation&apos;s scans, network and vulnerabilities straight
            away. This can&apos;t be undone — an admin would have to invite you
            again.
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
          Delete my account
        </Button>
      </section>
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
