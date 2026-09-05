import Pagination from '@/components/Pagination'
import Timestamp from '@/components/Timestamp'
import { HOME_ACTIVITY_PER_PAGE } from '@/api/home'
import type { components } from '@/types/openapi'

type HomeActivityItem = components['schemas']['HomeActivityItem']

type ActivityPanelProps = {
  data: HomeActivityItem[]
  total: number
  page: number
  onPageChange: (page: number) => void
  now?: Date
}

function ActivityPanel({
  data,
  total,
  page,
  onPageChange,
  now,
}: ActivityPanelProps) {
  const isBlank = data.length === 0

  return (
    <section
      id="home-activity-panel"
      className="flex flex-col gap-4 rounded-lg border border-rule bg-card p-6"
    >
      <h2
        data-testid="home-activity-heading"
        className="text-title-xs font-semibold"
      >
        Activity
      </h2>
      {isBlank ? (
        <p
          data-testid="home-activity-blank"
          className="text-body-md text-muted-foreground"
        >
          Nothing has been recorded yet.
        </p>
      ) : (
        <ul data-testid="home-activity-list" className="flex flex-col">
          {data.map((item, index) => (
            <li
              key={index}
              data-testid={`home-activity-row-${index}`}
              className="flex items-baseline gap-4"
            >
              <span
                data-testid={`home-activity-row-${index}-time`}
                className="w-26 shrink-0 text-caption-md text-muted-foreground tabular-nums"
              >
                <Timestamp value={item.occurred_at} now={now} />
              </span>
              <span
                data-testid={`home-activity-row-${index}-text`}
                className="min-w-0 flex-1 truncate text-body-md"
              >
                {item.text}
              </span>
            </li>
          ))}
        </ul>
      )}
      <Pagination
        page={page}
        perPage={HOME_ACTIVITY_PER_PAGE}
        total={total}
        onPageChange={onPageChange}
        testId="home-activity"
        label="Activity pages"
      />
    </section>
  )
}

export default ActivityPanel
