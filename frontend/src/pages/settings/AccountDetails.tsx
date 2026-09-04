import { useSession } from '@/auth/useSession'

function AccountDetails() {
  const { user } = useSession()

  if (!user) {
    return null
  }

  return (
    <section data-testid="settings-details" className="flex flex-col gap-4">
      <h2 className="text-title-sm">Your details</h2>
      <dl className="flex flex-col gap-2 text-body-md">
        <div className="flex min-w-0 gap-4">
          <dt className="shrink-0 text-muted-foreground">Email</dt>
          <dd
            data-testid="settings-details-email"
            className="min-w-0 break-words"
          >
            {user.email}
          </dd>
        </div>
        <div className="flex min-w-0 gap-4">
          <dt className="shrink-0 text-muted-foreground">Role</dt>
          <dd data-testid="settings-details-role" className="min-w-0">
            {user.role === 'admin' ? 'Admin' : 'Viewer'}
          </dd>
        </div>
      </dl>
    </section>
  )
}

export default AccountDetails
