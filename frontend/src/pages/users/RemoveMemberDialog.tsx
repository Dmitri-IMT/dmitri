import ConfirmByTyping from '@/components/ConfirmByTyping'

type RemoveMemberDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  email: string
  onConfirm: () => Promise<void>
  error?: string | null
}

function RemoveMemberDialog({
  open,
  onOpenChange,
  email,
  onConfirm,
  error = null,
}: RemoveMemberDialogProps) {
  return (
    <ConfirmByTyping
      open={open}
      onOpenChange={onOpenChange}
      heading={`Remove ${email}?`}
      body="They lose access immediately and their account is deleted. This can't be undone. You can invite them again later."
      expectedValue={email}
      confirmLabel="Remove"
      confirmPendingLabel="Removing…"
      onConfirm={onConfirm}
      error={error}
    />
  )
}

export default RemoveMemberDialog
