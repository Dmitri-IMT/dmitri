import { Button } from '@/components/ui/button'
import useI18n from '@/i18n/useI18n'

function HomeError({ onRetry }: { onRetry: () => void }) {
  const { t } = useI18n()
  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <p data-testid="home-error" className="text-title-md">
        {t('home.error')}
      </p>
      <Button
        type="button"
        variant="outline"
        data-testid="home-retry"
        onClick={onRetry}
      >
        {t('home.retry')}
      </Button>
    </div>
  )
}

export default HomeError
