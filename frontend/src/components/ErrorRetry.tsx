import { Button } from '@/components/ui/button'

type ErrorRetryProps = {
  message: string
  testId: string
  onRetry: () => void
  actionLabel?: string
}

function ErrorRetry({
  message,
  testId,
  onRetry,
  actionLabel = 'Retry',
}: ErrorRetryProps) {
  return (
    <div className="flex flex-col items-center gap-6 py-16 text-center">
      <p data-testid={testId} className="text-title-sm">
        {message}
      </p>
      <Button
        type="button"
        variant="outline"
        data-testid={`${testId}-retry`}
        onClick={onRetry}
      >
        {actionLabel}
      </Button>
    </div>
  )
}

export default ErrorRetry
