import { Button } from '@/components/ui/button'
import useI18n from '@/i18n/useI18n'
import { TIME_KEY, WHO_KEY } from '@/lib/fixTask'
import type { components } from '@/types/openapi'

export default function FixTaskSteps({
  task,
}: {
  task: components['schemas']['AIFixTask']
}) {
  const { t } = useI18n()
  return (
    <div className="flex flex-col gap-3">
      <p className="text-body-md font-semibold">{task.title}</p>
      <p className="text-caption-md text-ink-muted">
        {t(WHO_KEY[task.who])} · {t(TIME_KEY[task.time])} ·{' '}
        {t(task.fixes_fully ? 'finding.full' : 'finding.reduces')}
      </p>
      <ol className="flex list-decimal flex-col gap-2 pl-4 text-body-md">
        {task.steps.map((step, index) => (
          <li key={index}>{step}</li>
        ))}
      </ol>
      {task.sources.length > 0 && (
        <p className="text-body-sm text-ink-muted">
          {t('todo.sources')}{' '}
          {task.sources.map((source, index) => (
            <span key={source.url}>
              {index > 0 && ', '}
              <Button
                asChild
                variant="link"
                className="h-auto p-0 text-body-sm"
              >
                <a href={source.url} target="_blank" rel="noreferrer noopener">
                  {source.name}
                </a>
              </Button>
            </span>
          ))}
        </p>
      )}
      {task.fallback && (
        <p
          data-testid="finding-fix-fallback"
          className="border-t border-rule pt-3 text-body-sm"
        >
          {task.fallback}
        </p>
      )}
      <p className="text-body-sm text-ink-muted">{t('finding.check')}</p>
    </div>
  )
}
