import { http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import type { components } from '@/types/openapi'

type ScanDetailResponse = components['schemas']['ScanDetailResponse']

export const baseURL = 'http://localhost:8000/api/v1'

export function scansFail() {
  server.use(
    http.get(`${baseURL}/scans`, () => new HttpResponse(null, { status: 500 })),
  )
}

export function scanDetail(scan: ScanDetailResponse) {
  server.use(
    http.get(`${baseURL}/scans/:scanId`, () => HttpResponse.json(scan)),
  )
}

export function scanNotFound() {
  server.use(
    http.get(
      `${baseURL}/scans/:scanId`,
      () => new HttpResponse(null, { status: 404 }),
    ),
  )
}
