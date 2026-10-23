import type { ReactNode } from 'react'
import useI18n from '@/i18n/useI18n'

export default function ItSections({ children }: { children: ReactNode }) {
  const { t } = useI18n()
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-caption-md text-ink-muted">{t('it.title')}</h2>
      {children}
    </section>
  )
}
