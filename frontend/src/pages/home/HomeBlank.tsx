import { FirstScanCta, FirstScanNote } from '@/components/FirstScanCta'

function HomeBlank() {
  return (
    <div className="flex flex-col items-center gap-6 pt-24 text-center">
      <p data-testid="home-verdict" className="text-title-lg">
        No scans yet
      </p>
      <p
        data-testid="home-blank-body"
        className="text-body-md text-muted-foreground"
      >
        Your first scan finds the machines on your network and what needs
        fixing.
      </p>
      <FirstScanCta />
      <FirstScanNote />
    </div>
  )
}

export default HomeBlank
