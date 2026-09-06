import { HOME_EVENTS_PER_PAGE } from '@/api/home'
import HomeFeedPanel from '@/pages/home/HomeFeedPanel'
import type { components } from '@/types/openapi'

type HomeEvent = components['schemas']['HomeEvent']

type EventsPanelProps = {
  data: HomeEvent[]
  total: number
  page: number
  onPageChange: (page: number) => void
}

function EventsPanel({ data, total, page, onPageChange }: EventsPanelProps) {
  return (
    <HomeFeedPanel
      testId="home-events"
      title="Events"
      emptyText="Nothing to report right now."
      isBlank={data.length === 0}
      total={total}
      page={page}
      perPage={HOME_EVENTS_PER_PAGE}
      onPageChange={onPageChange}
      label="Events pages"
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
