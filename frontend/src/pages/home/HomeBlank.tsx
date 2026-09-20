import { FirstScanCta, FirstScanNote } from '@/components/FirstScanCta'
import useI18n from '@/i18n/useI18n'

function HomeBlank() {
  const { t } = useI18n()
  return (
    <div className="flex flex-col items-center gap-6 pt-24 text-center">
      <p data-testid="home-verdict" className="text-title-lg">
        {t('home.noScans')}
      </p>
      <p
        data-testid="home-blank-body"
        className="text-body-md text-muted-foreground"
      >
        {t('home.firstScanBody')}
      </p>
      <FirstScanCta />
      <FirstScanNote />
    </div>
  )
}

export default HomeBlank
