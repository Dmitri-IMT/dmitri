import Timestamp from '@/components/Timestamp'
import { HOME_ACTIVITY_PER_PAGE } from '@/api/home'
import HomeFeedPanel from '@/pages/home/HomeFeedPanel'
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
  return (
    <HomeFeedPanel
      testId="home-activity"
      title="Activity"
      emptyText="Nothing has been recorded yet."
      isBlank={data.length === 0}
      total={total}
      page={page}
      perPage={HOME_ACTIVITY_PER_PAGE}
      onPageChange={onPageChange}
      label="Activity pages"
    >
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
    </HomeFeedPanel>
  )
}

export default ActivityPanel
