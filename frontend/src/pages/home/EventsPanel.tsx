import { HOME_EVENTS_PER_PAGE } from '@/api/home'
import HomeFeedPanel from '@/pages/home/HomeFeedPanel'
import type { components } from '@/types/openapi'
import useI18n from '@/i18n/useI18n'

type HomeEvent = components['schemas']['HomeEvent']

type EventsPanelProps = {
  data: HomeEvent[]
  total: number
  page: number
  onPageChange: (page: number) => void
}

function EventsPanel({ data, total, page, onPageChange }: EventsPanelProps) {
  const { t } = useI18n()
  return (
    <HomeFeedPanel
      testId="home-events"
      title={t('home.events')}
      emptyText={t('home.eventsEmpty')}
      isBlank={data.length === 0}
      total={total}
      page={page}
      perPage={HOME_EVENTS_PER_PAGE}
      onPageChange={onPageChange}
      label={t('home.eventsPages')}
    >
      {data.map((event, index) => (
        <li
          key={index}
          data-testid={`home-events-row-${index}`}
          className="truncate text-body-md"
        >
          {event.text}
        </li>
      ))}
    </HomeFeedPanel>
  )
}

export default EventsPanel
