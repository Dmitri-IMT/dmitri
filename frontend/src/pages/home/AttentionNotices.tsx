import type { components } from '@/types/openapi'

type HomeNotice = components['schemas']['HomeNotice']

function noticeTestId(kind: HomeNotice['kind']): string {
  switch (kind) {
    case 'failed_scan':
      return 'home-item-scan'
    default: {
      const _exhaustive: never = kind
      return _exhaustive
    }
  }
}

function AttentionNotices({ notices }: { notices: HomeNotice[] }) {
  return (
    <>
      {notices.map((notice, index) => (
        <p
          key={`${notice.kind}-${index}`}
          data-testid={noticeTestId(notice.kind)}
          className="text-body-md text-muted-foreground"
        >
          {notice.text}
        </p>
      ))}
    </>
  )
}

export default AttentionNotices
