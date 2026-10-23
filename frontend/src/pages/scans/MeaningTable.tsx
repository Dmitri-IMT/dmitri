import TermHint from '@/components/TermHint'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import useI18n from '@/i18n/useI18n'
import { coverageCounts } from '@/lib/scanCoverage'
import type { components } from '@/types/openapi'

export default function MeaningTable({
  scan,
}: {
  scan: components['schemas']['ScanDetailResponse']
}) {
  const { t } = useI18n()
  const levels = ['critical', 'high', 'medium', 'low'] as const
  const counts = Object.fromEntries(
    levels.map((level) => [
      level,
      scan.findings.filter((finding) => finding.severity === level).length,
    ]),
  )
  const max = Math.max(1, ...Object.values(counts))
  const missing = coverageCounts(scan).machines
  return (
    <Card data-testid="meaning-table">
      <CardHeader>
        <h2 className="text-title-xs">{t('meaning.title')}</h2>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <table className="w-full text-left text-body-md">
          <thead>
            <tr className="text-caption-md text-ink-muted">
              {[
                'problems.level',
                'meaning.yours',
                'meaning.means',
                'meaning.act',
              ].map((key) => (
                <th key={key} scope="col" className="pb-4 font-normal">
                  {t(key as 'problems.level')}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {levels.map((level) => (
              <tr
                key={level}
                data-testid={`meaning-row-${level}`}
                className="border-t border-rule"
              >
                <th scope="row" className="py-4 pr-4">
                  <TermHint
                    term={level}
                    label={t('common.severity', { severity: level })}
                  >
                    <p className="font-semibold">
                      {t('common.severity', { severity: level })}
                    </p>
                    <p>{t(`hint.${level}`)}</p>
                  </TermHint>
                </th>
                <td className="w-48 pr-6">
                  <div className="flex items-center gap-3">
                    {counts[level] > 0 && (
                      <div
                        aria-hidden="true"
                        className={`h-3 shrink-0 rounded-xs ${level === 'critical' || level === 'high' ? 'bg-ink' : 'bg-edge'}`}
                        style={{
                          width: `${Math.max(4, (counts[level] / max) * 160)}px`,
                        }}
                      />
                    )}
                    <span
                      className={
                        counts[level] ? 'font-semibold' : 'text-ink-muted'
                      }
                    >
                      {counts[level]}
                    </span>
                  </div>
                </td>
                <td className="py-4 pr-6">{t(`meaning.${level}`)}</td>
                <td className={level === 'critical' ? 'font-semibold' : ''}>
                  {t(`meaning.when.${level}`)}
                </td>
              </tr>
            ))}
            {missing > 0 && (
              <tr
                data-testid="meaning-row-not-checked"
                className="border-t border-rule text-ink-muted"
              >
                <th scope="row" className="py-4 pr-4 font-normal">
                  <TermHint term="not-checked" label={t('meaning.notChecked')}>
                    <p>{t('hint.notChecked')}</p>
                  </TermHint>
                </th>
                <td>{missing}</td>
                <td className="pr-6">{t('meaning.notCheckedHelp')}</td>
                <td>{t('meaning.rescan')}</td>
              </tr>
            )}
          </tbody>
        </table>
        {scan.findings.length === 0 && (
          <p className="text-body-sm text-ink-muted">
            {t('common.noVulnerabilitiesInScan')} {t('todo.notProof')}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
