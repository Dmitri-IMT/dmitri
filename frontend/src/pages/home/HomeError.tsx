import { Button } from '@/components/ui/button'

function HomeError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <p data-testid="home-error" className="font-title text-title-md">
        Couldn&apos;t load your network&apos;s status.
      </p>
      <Button
        type="button"
        variant="outline"
        data-testid="home-retry"
        onClick={onRetry}
      >
        Retry
      </Button>
    </div>
  )
}

export default HomeError
