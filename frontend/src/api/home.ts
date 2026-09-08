import { apiClient } from './client'
import type { components } from '../types/openapi'

export type HomeSnapshot = components['schemas']['HomeSnapshot']

export interface HomePages {
  attentionPage: number
  eventsPage: number
  activityPage: number
}

export const HOME_ATTENTION_PER_PAGE = 8
export const HOME_EVENTS_PER_PAGE = 5
export const HOME_ACTIVITY_PER_PAGE = 8

export async function getHome(pages: HomePages): Promise<HomeSnapshot> {
  const response = await apiClient.get<HomeSnapshot>('/home', {
    params: {
      attention_page: pages.attentionPage,
      events_page: pages.eventsPage,
      activity_page: pages.activityPage,
    },
  })
  return response.data
}
