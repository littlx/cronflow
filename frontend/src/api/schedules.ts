import client from './client'
import type { Schedule, ScheduleCreate } from './types'

export function listSchedules() {
  return client.get<Schedule[]>('/schedules').then((r) => r.data)
}

export function createSchedule(payload: ScheduleCreate) {
  return client.post<Schedule>('/schedules', payload).then((r) => r.data)
}

export function updateSchedule(id: number, payload: Partial<ScheduleCreate>) {
  return client.put<Schedule>(`/schedules/${id}`, payload).then((r) => r.data)
}

export function deleteSchedule(id: number) {
  return client.delete(`/schedules/${id}`).then((r) => r.data)
}

export function toggleSchedule(id: number) {
  return client.post<Schedule>(`/schedules/${id}/toggle`).then((r) => r.data)
}
