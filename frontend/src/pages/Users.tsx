import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import PageHeader from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { revokeInvite } from '@/api/invites'
import { deleteUser, updateUserRole } from '@/api/users'
import { useOrgDirectory } from '@/hooks/useOrgDirectory'
import { useToast } from '@/hooks/useToast'
import DirectoryTable from '@/pages/users/DirectoryTable'
import InviteDialog from '@/pages/users/InviteDialog'
import RemoveMemberDialog from '@/pages/users/RemoveMemberDialog'
import RevokeDialog from '@/pages/users/RevokeDialog'
import RoleChangeDialog from '@/pages/users/RoleChangeDialog'
import { ROLE_NOUN, type Role } from '@/lib/directory'
import useI18n from '@/i18n/useI18n'

type PendingRoleChange = { id: string; email: string; nextRole: Role }

const ROLE_ERROR = "Couldn't change that role."
const REMOVE_ERROR = "Couldn't remove that person."
const REVOKE_ERROR = "Couldn't revoke that invite."

function Users() {
  const directory = useOrgDirectory()
  const { t } = useI18n()
  const queryClient = useQueryClient()
  const { show } = useToast()
  const [pendingRole, setPendingRole] = useState<PendingRoleChange | null>(null)
  const [roleError, setRoleError] = useState<string | null>(null)
  const [pendingRemoval, setPendingRemoval] = useState<{
    id: string
    email: string
  } | null>(null)
  const [removeError, setRemoveError] = useState<string | null>(null)
  const [pendingRevoke, setPendingRevoke] = useState<{
    id: string
    email: string
  } | null>(null)
  const [revokeError, setRevokeError] = useState<string | null>(null)
  const [inviteOpen, setInviteOpen] = useState(false)
  const canInvite = directory.state === 'ready' || directory.state === 'blank'

  async function handleRoleConfirm() {
    if (!pendingRole) {
      return
    }
    setRoleError(null)
    try {
      await updateUserRole(pendingRole.id, { role: pendingRole.nextRole })
      show(`${pendingRole.email} is now ${ROLE_NOUN[pendingRole.nextRole]}.`)
      setPendingRole(null)
      await queryClient.invalidateQueries({ queryKey: ['org'] })
    } catch {
      setRoleError(ROLE_ERROR)
    }
  }

  async function handleRemoveConfirm() {
    if (!pendingRemoval) {
      return
    }
    setRemoveError(null)
    try {
      await deleteUser(pendingRemoval.id)
      show(`${pendingRemoval.email} was removed.`)
      setPendingRemoval(null)
      await queryClient.invalidateQueries({ queryKey: ['org'] })
    } catch {
      setRemoveError(REMOVE_ERROR)
    }
  }

  async function handleRevokeConfirm() {
    if (!pendingRevoke) {
      return
    }
    setRevokeError(null)
    try {
      await revokeInvite(pendingRevoke.id)
      show(`The invite to ${pendingRevoke.email} was revoked.`)
      setPendingRevoke(null)
      await queryClient.invalidateQueries({ queryKey: ['org'] })
    } catch {
      setRevokeError(REVOKE_ERROR)
    }
  }

  return (
    <div className="flex flex-col gap-12">
      <PageHeader title={t('nav.users')} />
      <DirectoryTable
        directory={directory}
        onRoleChange={(row, next) =>
          setPendingRole({ id: row.id, email: row.email, nextRole: next })
        }
        onRemove={(row) => setPendingRemoval({ id: row.id, email: row.email })}
        onRevoke={(row) => setPendingRevoke({ id: row.id, email: row.email })}
      />
      {canInvite && (
        <div className="flex justify-end">
          <Button
            type="button"
            size="lg"
            onClick={() => setInviteOpen(true)}
            data-testid="invite-open"
          >
            {t('users.invite')}
          </Button>
        </div>
      )}
      {inviteOpen && (
        <InviteDialog
          open
          onOpenChange={setInviteOpen}
          onDone={() => {
            setInviteOpen(false)
            void queryClient.invalidateQueries({ queryKey: ['org'] })
          }}
        />
      )}
      {pendingRole && (
        <RoleChangeDialog
          open
          onOpenChange={(open) => {
            if (!open) {
              setPendingRole(null)
              setRoleError(null)
            }
          }}
          email={pendingRole.email}
          nextRole={pendingRole.nextRole}
          onConfirm={handleRoleConfirm}
          error={roleError}
        />
      )}
      {pendingRemoval && (
        <RemoveMemberDialog
          open
          onOpenChange={(open) => {
            if (!open) {
              setPendingRemoval(null)
              setRemoveError(null)
            }
          }}
          email={pendingRemoval.email}
          onConfirm={handleRemoveConfirm}
          error={removeError}
        />
      )}
      {pendingRevoke && (
        <RevokeDialog
          open
          onOpenChange={(open) => {
            if (!open) {
              setPendingRevoke(null)
              setRevokeError(null)
            }
          }}
          email={pendingRevoke.email}
          onConfirm={handleRevokeConfirm}
          error={revokeError}
        />
      )}
    </div>
  )
}

export default Users
