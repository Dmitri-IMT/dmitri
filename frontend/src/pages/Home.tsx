import { useHomeReview } from '@/hooks/useHomeReview'
import Ornament from '@/components/Ornament'
import Verdict from '@/pages/home/Verdict'
import FindingDeck from '@/pages/home/FindingDeck'
import ReviewItemCard from '@/pages/home/ReviewItemCard'
import HomeBlank from '@/pages/home/HomeBlank'
import HomeError from '@/pages/home/HomeError'
import HomeFooter from '@/pages/home/HomeFooter'

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
        <>
          <div className="flex flex-col items-center gap-6 text-center">
            <Verdict
              reviewCount={review.reviewCount}
              latestSuccessfulScan={review.latestSuccessfulScan}
            />
            <Ornament />
          </div>
          {review.latestSuccessfulScan && (
            <HomeFooter scan={review.latestSuccessfulScan} />
          )}
        </>
      )
    case 'pending':
      return (
        <>
          <div className="flex flex-col gap-8">
            <Verdict
              reviewCount={review.reviewCount}
              latestSuccessfulScan={review.latestSuccessfulScan}
            />
            <div className="flex flex-col gap-6">
              <FindingDeck findings={review.deckFindings} />
              {review.scanItem && <ReviewItemCard variant="scan" />}
              {review.coverageItem && (
                <ReviewItemCard
                  variant="coverage"
                  days={review.coverageItem.daysSinceLastSuccess}
                />
              )}
            </div>
          </div>
          {review.latestSuccessfulScan && (
            <HomeFooter scan={review.latestSuccessfulScan} />
          )}
        </>
      )
  }
}

export default Home
