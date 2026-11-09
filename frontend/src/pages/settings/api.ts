import { request } from '../../shared/request'
import type { StudyAvailability } from './availability'

export type AvailabilityResponse = {
  weekday_minutes: StudyAvailability
  saved: boolean
}

const PATH = '/api/me/study-availability'

export function getStudyAvailability(signal?: AbortSignal) {
  return request<AvailabilityResponse>(PATH, { signal })
}

export function putStudyAvailability(value: StudyAvailability) {
  return request<AvailabilityResponse>(PATH, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ weekday_minutes: value }),
  })
}