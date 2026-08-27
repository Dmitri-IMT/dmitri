import { http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import type { components } from '@/types/openapi'

type HostDetailResponse = components['schemas']['HostDetailResponse']
type FindingRecord = components['schemas']['FindingRecord']
type FindingListResponse = components['schemas']['FindingListResponse']

export const baseURL = 'http://localhost:8000/api/v1'

export function hostsFail() {
  server.use(
    http.get(`${baseURL}/hosts`, () => new HttpResponse(null, { status: 500 })),
  )
}

export function hostDetail(
  host: HostDetailResponse,
  findings: FindingRecord[],
) {
  server.use(
    http.get(`${baseURL}/hosts/:hostId`, () => HttpResponse.json(host)),
    http.get(`${baseURL}/findings`, ({ request }) => {
      const params = new URL(request.url).searchParams
      const hostId = params.get('host_id')
      const data = findings.filter((finding) => finding.host_id === hostId)
      return HttpResponse.json({
        data,
        total: data.length,
        page: Number(params.get('page') ?? 1),
      } satisfies FindingListResponse)
    }),
  )
}

export function hostNotFound() {
  server.use(
    http.get(
      `${baseURL}/hosts/:hostId`,
      () => new HttpResponse(null, { status: 404 }),
    ),
  )
}
