import EmptyState from '@/components/EmptyState'

function DevicesBlank() {
  return (
    <EmptyState
      heading="No box connected yet"
      body="Your installer connects the box on site; it appears here once it comes online."
      testId="devices-blank"
      note={
        <p
          data-testid="devices-blank-note"
          className="text-body-sm text-muted-foreground"
        >
          Contact whoever installed Dmitri if you were expecting one.
        </p>
      }
    />
  )
}

export default DevicesBlank
