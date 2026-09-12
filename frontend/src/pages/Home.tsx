import { useState } from 'react'
import type { ReactNode } from 'react'
import LoadingSkeleton from '@/components/LoadingSkeleton'
import { HOME_ATTENTION_PER_PAGE } from '@/api/home'
import { useHome } from '@/hooks/useHome'
import AttentionNotices from '@/pages/home/AttentionNotices'
import AttentionTable from '@/pages/home/AttentionTable'
import Verdict from '@/pages/home/Verdict'
import HomeBlank from '@/pages/home/HomeBlank'
import HomeError from '@/pages/home/HomeError'
import { HOME_PANEL_CHROME } from '@/pages/home/HomeFeedPanel'
import HomeAIOverview from '@/pages/home/HomeAIOverview'
import HomeSidePanels from '@/pages/home/HomeSidePanels'

function HomeLoading() {
  return (
    <div data-testid="home-loading" className="flex flex-col gap-12">
      <table className="w-full table-fixed border-collapse">
        <LoadingSkeleton rows={HOME_ATTENTION_PER_PAGE} columns={3} />
      </table>
      <div className="grid grid-cols-2 gap-8">
        {Array.from({ length: 2 }, (_, index) => (
          <div key={index} className={HOME_PANEL_CHROME}>
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

  if (home.state === 'loading') {
    return (
      <div data-testid="home-page" className="flex flex-col gap-12">
        <HomeLoading />
      </div>
    )
  }

  if (home.state === 'error') {
    return (
      <div data-testid="home-page" className="flex flex-col py-16">
        <HomeError onRetry={home.retry} />
      </div>
    )
  }

  const { snapshot } = home

  // Only the attention column differs between the three snapshot states. The
  // shell and the feed panels below it are the same page in all three.
  let attention: ReactNode
  if (home.state === 'blank') {
    attention = <HomeBlank />
  } else {
    const verdict = (
      <Verdict
        reviewCount={snapshot.review_count}
        latestSuccessfulScan={snapshot.latest_successful_scan}
      />
    )
    attention =
      home.state === 'clear' ? (
        verdict
      ) : (
        <>
          <div className="flex flex-col gap-2">
            {verdict}
            <AttentionNotices notices={snapshot.notices} />
          </div>
          {/* AttentionTable omits the table when empty and Pagination hides
              itself on one page, so this needs no guard of its own. */}
          <AttentionTable
            findings={snapshot.attention.data}
            total={snapshot.attention.total}
            page={snapshot.attention.page}
            onPageChange={setAttentionPage}
          />
        </>
      )
  }

  return (
    <div data-testid="home-page" className="flex flex-col gap-12">
      {attention}
      {snapshot.latest_successful_scan && (
        <HomeAIOverview scanId={snapshot.latest_successful_scan.scan_id} />
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

export default Home
