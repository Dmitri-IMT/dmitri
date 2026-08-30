import { FirstScanCta, FirstScanNote } from '@/components/FirstScanCta'
import Ornament from '@/components/Ornament'

function HomeBlank() {
  return (
    <div className="flex flex-col items-center gap-6 text-center">
      <p data-testid="home-verdict" className="font-title text-title-lg">
        No scans yet.
      </p>
      <p
        data-testid="home-blank-body"
        className="text-body-md text-muted-foreground"
      >
        Dmitri scans your network for devices and known vulnerabilities, then
        reports anything worth your attention here.
      </p>
      <FirstScanCta />
      <FirstScanNote />
      <Ornament />
    </div>
  )
}

export default HomeBlank
