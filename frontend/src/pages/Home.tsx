import { useHomeReview } from '@/hooks/useHomeReview'
import AttentionNotices from '@/pages/home/AttentionNotices'
import AttentionTable from '@/pages/home/AttentionTable'
import Verdict from '@/pages/home/Verdict'
import HomeBlank from '@/pages/home/HomeBlank'
import HomeError from '@/pages/home/HomeError'

function Home() {
  const review = useHomeReview()

  switch (review.state) {
    case 'loading':
      return null
    case 'blank':
      return <HomeBlank />
    case 'error':
      return <HomeError onRetry={review.retry} />
    case 'clear':
      return (
        <div className="flex flex-col pt-24">
          <Verdict
            reviewCount={review.reviewCount}
            latestSuccessfulScan={review.latestSuccessfulScan}
          />
        </div>
      )
    case 'pending':
      return (
        <div className="flex flex-col gap-12">
          <div className="flex flex-col gap-2">
            <Verdict
              reviewCount={review.reviewCount}
              latestSuccessfulScan={review.latestSuccessfulScan}
            />
            <AttentionNotices
              scanItem={review.scanItem}
              coverageItem={review.coverageItem}
            />
          </div>
          <AttentionTable findings={review.deckFindings} />
        </div>
      )
  }
}

export default Home
