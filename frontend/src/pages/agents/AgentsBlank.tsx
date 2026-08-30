import EmptyState from '@/components/EmptyState'

function AgentsBlank() {
  return (
    <EmptyState
      heading="No Pi connected yet."
      body="Dmitri scans your network from a small box installed on site. Your installer sets it up — once it's online, it shows up here and you can run your first scan."
      testId="agents-blank"
      note={
        <p
          data-testid="agents-blank-note"
          className="text-body-sm text-muted-foreground"
        >
          Contact whoever installed Dmitri if you were expecting to see one.
        </p>
      }
    />
  )
}

export default AgentsBlank
