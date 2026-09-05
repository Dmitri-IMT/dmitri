import { useState } from 'react'
import LoadingSkeleton from '@/components/LoadingSkeleton'
import { HOME_ATTENTION_PER_PAGE } from '@/api/home'
import { useHome } from '@/hooks/useHome'
import AttentionNotices from '@/pages/home/AttentionNotices'
import AttentionTable from '@/pages/home/AttentionTable'
import Verdict from '@/pages/home/Verdict'
import HomeBlank from '@/pages/home/HomeBlank'
import HomeError from '@/pages/home/HomeError'
import HomeSidePanels from '@/pages/home/HomeSidePanels'

function HomeLoading() {
  return (
    <div data-testid="home-loading" className="flex flex-col gap-12">
      <table className="w-full table-fixed border-collapse">
        <LoadingSkeleton rows={HOME_ATTENTION_PER_PAGE} columns={3} />
      </table>
      <div className="grid grid-cols-2 gap-8">
        {Array.from({ length: 2 }, (_, index) => (
          <div
            key={index}
            className="flex flex-col gap-4 rounded-lg border border-rule bg-card p-6"
          >
            <span className="block h-4 w-1/4 bg-border" />
            {Array.from({ length: 3 }, (_, row) => (
              <span key={row} className="block h-3 w-3/4 bg-border" />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

function Home() {
  const [attentionPage, setAttentionPage] = useState(1)
  const [eventsPage, setEventsPage] = useState(1)
  const [activityPage, setActivityPage] = useState(1)

  const home = useHome({ attentionPage, eventsPage, activityPage })

  switch (home.state) {
    case 'loading':
      return (
        <div data-testid="home-page" className="flex flex-col gap-12">
          <HomeLoading />
        </div>
      )
    case 'error':
      return (
        <div data-testid="home-page" className="flex flex-col py-16">
          <HomeError onRetry={home.retry} />
        </div>
      )
    case 'blank': {
      const { snapshot } = home
      return (
        <div data-testid="home-page" className="flex flex-col gap-12">
          <HomeBlank />
          <HomeSidePanels
            events={snapshot.events}
            activity={snapshot.activity}
            onEventsPageChange={setEventsPage}
            onActivityPageChange={setActivityPage}
          />
        </div>
      )
    }
    case 'clear': {
      const { snapshot } = home
      return (
        <div data-testid="home-page" className="flex flex-col gap-12">
          <Verdict
            reviewCount={snapshot.review_count}
            latestSuccessfulScan={snapshot.latest_successful_scan}
          />
          <HomeSidePanels
            events={snapshot.events}
            activity={snapshot.activity}
            onEventsPageChange={setEventsPage}
            onActivityPageChange={setActivityPage}
          />
        </div>
      )
    }
    case 'pending': {
      const { snapshot } = home
      const showAttentionBlock =
        snapshot.attention.data.length > 0 ||
        snapshot.attention.total > HOME_ATTENTION_PER_PAGE

      return (
        <div data-testid="home-page" className="flex flex-col gap-12">
          <div className="flex flex-col gap-2">
            <Verdict
              reviewCount={snapshot.review_count}
              latestSuccessfulScan={snapshot.latest_successful_scan}
            />
            <AttentionNotices notices={snapshot.notices} />
          </div>
          {showAttentionBlock && (
            <div className="flex flex-col gap-4">
              <AttentionTable
                findings={snapshot.attention.data}
                total={snapshot.attention.total}
                page={snapshot.attention.page}
                onPageChange={setAttentionPage}
              />
            </div>
          )}
          <HomeSidePanels
            events={snapshot.events}
            activity={snapshot.activity}
            onEventsPageChange={setEventsPage}
            onActivityPageChange={setActivityPage}
          />
        </div>
      )
    }
    default: {
      const _exhaustive: never = home
      return _exhaustive
    }
  }
}

export default Home
