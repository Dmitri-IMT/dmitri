import { useState } from 'react'
import { Dialog } from 'radix-ui'
import { readApiError } from '@/api/apiError'
import { createInvite } from '@/api/invites'
import DialogShell from '@/components/DialogShell'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { Role } from '@/lib/directory'
import type { components } from '@/types/openapi'

type InviteCreatedResponse = components['schemas']['InviteCreatedResponse']

type InviteDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  onDone: () => void
}

const ALREADY_MEMBER = 'That person is already in your organization.'
const ALREADY_PENDING =
  'That address already has an invite waiting. Revoke it first if you need to send a new one.'
const GENERIC = "Couldn't create the invite."

function expiryPhrase(expiresAt: string): string {
  const hours = Math.max(
    1,
    Math.round((new Date(expiresAt).getTime() - Date.now()) / (1000 * 60 * 60)),
  )
  return `${hours} ${hours === 1 ? 'hour' : 'hours'}`
}

function InviteDialog({ open, onOpenChange, onDone }: InviteDialogProps) {
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Role>('viewer')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<
    (InviteCreatedResponse & { email: string }) | null
  >(null)
  const [copied, setCopied] = useState(false)

  function reset() {
    setEmail('')
    setRole('viewer')
    setError(null)
    setCreated(null)
    setCopied(false)
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (isSubmitting) {
      return
    }
    setIsSubmitting(true)
    setError(null)
    try {
      const response = await createInvite({ email, role })
      setCreated({ ...response, email })
    } catch (err) {
      const { status, code } = readApiError(err)
      if (status === 400 && code === 'email_already_member') {
        setError(ALREADY_MEMBER)
      } else if (status === 409 && code === 'invite_already_pending') {
        setError(ALREADY_PENDING)
      } else {
        setError(GENERIC)
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleCopy() {
    if (!created) {
      return
    }
    await navigator.clipboard?.writeText(inviteLink(created.invite_token))
    setCopied(true)
  }

  return (
    <DialogShell
      open={open}
      onOpenChange={onOpenChange}
      testId="invite-dialog"
      size="sm"
      locked={isSubmitting}
    >
      {created ? (
        <div
          data-testid="invite-created"
          className="flex flex-col gap-4"
          key="created"
        >
          <Dialog.Title className="font-title text-title-sm">
            Invite sent.
          </Dialog.Title>
          <Dialog.Description className="max-w-prose text-body-md text-muted-foreground">
            We emailed an invite to {created.email}. It works once, and expires
            in {expiryPhrase(created.expires_at)}.
          </Dialog.Description>
          <p className="text-body-md">Or send them this link yourself:</p>
          <p
            data-testid="invite-link"
            className="border border-input p-2 text-body-sm break-all"
          >
            {inviteLink(created.invite_token)}
          </p>
          <div className="flex justify-end">
            <Button
              type="button"
              variant="outline"
              onClick={handleCopy}
              data-testid="invite-copy"
            >
              {copied ? 'Copied' : 'Copy link'}
            </Button>
          </div>
          <p className="max-w-prose text-body-sm text-muted-foreground">
            This is the only time you&apos;ll see this link. If they never get
            the email, copy it now.
          </p>
          <div className="flex items-center justify-between gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={reset}
              data-testid="invite-again"
            >
              Invite someone else
            </Button>
            <Button
              type="button"
              onClick={() => {
                reset()
                onDone()
              }}
              data-testid="invite-done"
            >
              Done
            </Button>
          </div>
        </div>
      ) : (
        <form
          onSubmit={handleSubmit}
          className="flex flex-col gap-4"
          key="form"
        >
          <Dialog.Title className="font-title text-title-sm">
            Invite a user
          </Dialog.Title>
          <Dialog.Description className="max-w-prose text-body-md text-muted-foreground">
            Create a link that lets someone join your organization.
          </Dialog.Description>
          <div className="flex flex-col gap-1">
            <Label htmlFor="invite-email">Email</Label>
            <Input
              id="invite-email"
              type="email"
              required
              autoFocus
              autoComplete="off"
              aria-invalid={error !== null}
              aria-describedby="invite-error"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              data-testid="invite-email"
            />
            <p
              id="invite-error"
              role="alert"
              data-testid="invite-error"
              className="text-body-sm text-destructive"
            >
              {error}
            </p>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="invite-role">Role</Label>
            <p
              id="invite-role-note"
              data-testid="invite-role-note"
              className="max-w-prose text-caption-md text-muted-foreground"
            >
              A viewer can see scans, hosts and findings. An admin can also run
              scans and invite people.
            </p>
            <Select
              value={role}
              onValueChange={(next) => setRole(next as Role)}
            >
              <SelectTrigger
                id="invite-role"
                data-testid="invite-role"
                aria-describedby="invite-role-note"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="viewer">Viewer</SelectItem>
                <SelectItem value="admin">Admin</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex justify-end gap-2">
            {!isSubmitting && (
              <Dialog.Close asChild>
                <Button type="button" variant="outline">
                  Cancel
                </Button>
              </Dialog.Close>
            )}
            <Button
              type="submit"
              disabled={isSubmitting}
              data-testid="invite-submit"
            >
              {isSubmitting
                ? 'Creating…'
                : error === GENERIC
                  ? 'Try again'
                  : 'Create invite link'}
            </Button>
          </div>
        </form>
      )}
    </DialogShell>
  )
}

function inviteLink(token: string): string {
  return `${window.location.origin}/invite?token=${token}`
}

export default InviteDialog
