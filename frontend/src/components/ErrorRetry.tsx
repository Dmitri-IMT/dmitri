import { Button } from '@/components/ui/button'

type ErrorRetryProps = {
  message: string
  testId: string
  onRetry: () => void
}

function ErrorRetry({ message, testId, onRetry }: ErrorRetryProps) {
  return (
    <div className="flex flex-col items-center gap-6 py-16 text-center">
      <p data-testid={testId} className="font-title text-title-sm">
        {message}
      </p>
      <Button
        type="button"
        variant="outline"
        data-testid={`${testId}-retry`}
        onClick={onRetry}
      >
        Retry
      </Button>
    </div>
  )
}

export default ErrorRetry
