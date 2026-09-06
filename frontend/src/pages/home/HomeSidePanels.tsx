import type { components } from '@/types/openapi'
import ActivityPanel from './ActivityPanel'
import EventsPanel from './EventsPanel'

type HomeEventsPage = components['schemas']['HomeEventsPage']
type HomeActivityPage = components['schemas']['HomeActivityPage']

type HomeSidePanelsProps = {
  events: HomeEventsPage
  activity: HomeActivityPage
  onEventsPageChange: (page: number) => void
  onActivityPageChange: (page: number) => void
  now?: Date
}

function HomeSidePanels({
  events,
  activity,
  onEventsPageChange,
  onActivityPageChange,
  now,
}: HomeSidePanelsProps) {
  return (
    <div data-testid="home-side-panels" className="grid grid-cols-2 gap-8">
      <EventsPanel
        data={events.data}
        total={events.total}
        page={events.page}
        onPageChange={onEventsPageChange}
      />
      <ActivityPanel
        data={activity.data}
        total={activity.total}
        page={activity.page}
        onPageChange={onActivityPageChange}
        now={now}
      />
    </div>
  )
}

export default HomeSidePanels
