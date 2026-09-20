import { Button } from '@/components/ui/button'
import { UI_COPY } from '@/lib/copy'
import { useLanguage } from '@/i18n/LanguageProvider'

type ErrorRetryProps = {
  message: string
  testId: string
  onRetry: () => void
}

function ErrorRetry({ message, testId, onRetry }: ErrorRetryProps) {
  const { language } = useLanguage()

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="flex flex-col items-center gap-6 px-4 py-16 text-center"
    >
      <p data-testid={testId} className="text-title-sm">
        {message}
      </p>
      <Button
        type="button"
        variant="outline"
        data-testid={`${testId}-retry`}
        onClick={onRetry}
      >
        {UI_COPY[language].retry}
      </Button>
    </div>
  )
}

export default ErrorRetry
