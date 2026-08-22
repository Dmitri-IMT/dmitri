import { http, HttpResponse } from 'msw'
import { server } from '@/test/setup'
import type { components } from '@/types/openapi'

export type OrgMember = components['schemas']['OrgMember']
export type PendingInvite = components['schemas']['PendingInvite']
type UserProfileResponse = components['schemas']['UserProfileResponse']

export const baseURL = 'http://localhost:8000/api/v1'

export function directory(members: OrgMember[], invites: PendingInvite[]) {
  server.use(
    http.get(`${baseURL}/users`, () => HttpResponse.json({ data: members })),
    http.get(`${baseURL}/invites`, () => HttpResponse.json({ data: invites })),
  )
}

export function signedInAs(profile: UserProfileResponse) {
  server.use(http.get(`${baseURL}/users/me`, () => HttpResponse.json(profile)))
}
