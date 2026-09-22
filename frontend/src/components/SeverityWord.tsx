import EmptyMark from '@/components/EmptyMark'
import useI18n from '@/i18n/useI18n'
import type { components } from '@/types/openapi'

type Severity = components['schemas']['Severity']

function SeverityWord({ severity }: { severity: Severity | null | undefined }) {
  const { t } = useI18n()
  if (severity == null) return <EmptyMark />
  return (
    <span className="font-semibold">{t('common.severity', { severity })}</span>
  )
}

export default SeverityWord
