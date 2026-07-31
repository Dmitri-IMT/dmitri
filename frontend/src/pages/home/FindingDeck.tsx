import { useState, type KeyboardEvent } from 'react'
import { Button } from '@/components/ui/button'
import ReviewItemCard from '@/pages/home/ReviewItemCard'
import type { components } from '@/types/openapi'

type FindingRecord = components['schemas']['FindingRecord']

function FindingDeck({ findings }: { findings: FindingRecord[] }) {
  const [index, setIndex] = useState(0)
  const [trackedFindings, setTrackedFindings] = useState(findings)

  if (findings !== trackedFindings) {
    setTrackedFindings(findings)
    setIndex(0)
  }

  if (findings.length === 0) {
    return null
  }

  const canGoPrevious = index > 0
  const canGoNext = index < findings.length - 1

  function goPrevious() {
    if (canGoPrevious) setIndex((current) => current - 1)
  }

  function goNext() {
    if (canGoNext) setIndex((current) => current + 1)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'ArrowLeft') {
      goPrevious()
    } else if (event.key === 'ArrowRight') {
      goNext()
    }
  }

  return (
    <div
      data-testid="home-deck"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      className="flex flex-col gap-4"
    >
      <div data-testid="home-deck-card" aria-live="polite">
        <ReviewItemCard variant="finding" finding={findings[index]} />
      </div>
      {findings.length > 1 && (
        <div className="flex items-center justify-between gap-4">
          {canGoPrevious ? (
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label="Previous finding"
              data-testid="home-deck-prev"
              onClick={goPrevious}
            >
              ←
            </Button>
          ) : (
            <div className="size-8" aria-hidden="true" />
          )}
          <p
            data-testid="home-deck-position"
            className="text-body-md text-muted-foreground"
          >
            {index + 1} of {findings.length}
          </p>
          {canGoNext ? (
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label="Next finding"
              data-testid="home-deck-next"
              onClick={goNext}
            >
              →
            </Button>
          ) : (
            <div className="size-8" aria-hidden="true" />
          )}
        </div>
      )}
    </div>
  )
}

export default FindingDeck
