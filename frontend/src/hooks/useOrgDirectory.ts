import { useQuery } from '@tanstack/react-query'
import { listPendingInvites } from '@/api/invites'
import { listOrgMembers } from '@/api/users'
import { useSession } from '@/auth/useSession'
import { mergeDirectory, type DirectoryRow } from '@/lib/directory'

export type OrgDirectory =
  | { state: 'loading' }
  | { state: 'error'; retry: () => void }
  | { state: 'blank'; rows: DirectoryRow[] }
  | { state: 'ready'; rows: DirectoryRow[] }

export function useOrgDirectory(): OrgDirectory {
  const { user } = useSession()

  const membersQuery = useQuery({
    queryKey: ['org', 'members'],
    queryFn: listOrgMembers,
  })

  const invitesQuery = useQuery({
    queryKey: ['org', 'invites'],
    queryFn: listPendingInvites,
  })

  if (membersQuery.isError || invitesQuery.isError) {
    const retry = () => {
      membersQuery.refetch()
      invitesQuery.refetch()
    }
    return { state: 'error', retry }
  }
  if (membersQuery.isPending || invitesQuery.isPending) {
    return { state: 'loading' }
  }

  const members = membersQuery.data.data
  const invites = invitesQuery.data.data
  const rows = mergeDirectory(members, invites, user?.user_id ?? '')

  return members.length <= 1 && invites.length === 0
    ? { state: 'blank', rows }
    : { state: 'ready', rows }
}
