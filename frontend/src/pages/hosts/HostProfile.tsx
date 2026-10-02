import Disclosure from '@/components/Disclosure'
import { MACHINE_TYPE_LABELS } from '@/lib/machineType'
import type { components } from '@/types/openapi'

type HostDetailResponse = components['schemas']['HostDetailResponse']
type DeviceProfile = components['schemas']['DeviceProfilePayload']
type AssessmentConfidence = components['schemas']['AssessmentConfidence']

const CONFIDENCE_LABEL: Record<AssessmentConfidence, string> = {
  unknown: 'Unknown',
  low: 'Low',
  medium: 'Medium',
  high: 'High',
}

function profileValue(value: string | null | undefined): string {
  return value ?? 'Unknown'
}

function ProfileEvidence({ profile }: { profile: DeviceProfile }) {
  return (
    <div className="flex max-w-prose flex-col gap-4 pt-3 text-body-md">
      {profile.evidence.length > 0 && (
        <ul className="flex flex-col gap-2">
          {profile.evidence.map((item, index) => (
            <li key={`${item.kind}-${item.source}-${index}`}>
              {item.source}: {item.value}
            </li>
          ))}
        </ul>
      )}
      {profile.conflicts.length > 0 && (
        <ul
          data-testid="host-profile-conflicts"
          className="flex flex-col gap-2"
        >
          {profile.conflicts.map((conflict, index) => (
            <li key={`${conflict}-${index}`}>
              <span aria-hidden="true">⚠ </span>
              Conflicting evidence: {conflict}
            </li>
          ))}
        </ul>
      )}
      {profile.limitations.length > 0 && (
        <ul
          data-testid="host-profile-limitations"
          className="flex flex-col gap-2 text-muted-foreground"
        >
          {profile.limitations.map((limitation, index) => (
            <li key={`${limitation}-${index}`}>Limitation: {limitation}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function HostProfile({ host }: { host: HostDetailResponse }) {
  const profile =
    host.assessment_status === 'unavailable' ? null : host.device_profile

  return (
    <div className="flex flex-col gap-6">
      <dl className="grid grid-cols-1 gap-3 text-body-md sm:grid-cols-2 sm:gap-8">
        <dt className="text-muted-foreground">Operating system</dt>
        <dd data-testid="host-operating-system">
          {host.operating_system?.name ?? 'Unknown'}
        </dd>
        {host.operating_system && (
          <>
            <dt className="text-muted-foreground">Nmap accuracy</dt>
            <dd data-testid="host-operating-system-accuracy">
              {host.operating_system.accuracy}%
            </dd>
          </>
        )}
        {profile && (
          <>
            <dt className="text-muted-foreground">Likely type</dt>
            <dd>{MACHINE_TYPE_LABELS[host.machine_type] ?? 'Unknown'}</dd>
            <dt className="text-muted-foreground">Manufacturer</dt>
            <dd>{profileValue(profile.manufacturer)}</dd>
            <dt className="text-muted-foreground">Product family</dt>
            <dd>{profileValue(profile.product_family)}</dd>
            <dt className="text-muted-foreground">Model</dt>
            <dd>{profileValue(profile.model)}</dd>
            <dt className="text-muted-foreground">Profile confidence</dt>
            <dd>{CONFIDENCE_LABEL[profile.confidence]}</dd>
          </>
        )}
      </dl>
      {profile ? (
        <Disclosure
          label="Why this profile?"
          testId="host-profile-evidence"
          caretTestId="host-profile-evidence-caret"
        >
          <ProfileEvidence profile={profile} />
        </Disclosure>
      ) : (
        <p data-testid="host-profile-unavailable" className="text-body-md">
          Unavailable. Device profiling is not available for this scan. Re-run
          the scan to produce this data.
        </p>
      )}
    </div>
  )
}

export default HostProfile
