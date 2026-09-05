import Pagination from '@/components/Pagination'
import { HOME_EVENTS_PER_PAGE } from '@/api/home'
import type { components } from '@/types/openapi'

type HomeEvent = components['schemas']['HomeEvent']

type EventsPanelProps = {
  data: HomeEvent[]
  total: number
  page: number
  onPageChange: (page: number) => void
}

function EventsPanel({ data, total, page, onPageChange }: EventsPanelProps) {
  const isBlank = data.length === 0

  return (
    <section
      id="home-events-panel"
      className="flex flex-col gap-4 rounded-lg border border-rule bg-card p-6"
    >
      <h2
        data-testid="home-events-heading"
        className="text-title-xs font-semibold"
      >
        Events
      </h2>
      {isBlank ? (
        <p
          data-testid="home-events-blank"
          className="text-body-md text-muted-foreground"
        >
          Nothing to report right now.
        </p>
      ) : (
        <ul data-testid="home-events-list" className="flex flex-col">
          {data.map((event, index) => (
            <li
              key={index}
              data-testid={`home-events-row-${index}`}
              className="truncate text-body-md"
            >
              {event.text}
            </li>
          ))}
        </ul>
      )}
      <Pagination
        page={page}
        perPage={HOME_EVENTS_PER_PAGE}
        total={total}
        onPageChange={onPageChange}
        testId="home-events"
        label="Events pages"
      />
    </section>
  )
}

export default EventsPanel
