import client from './client'
import type { NotificationConfig, NotificationConfigCreate, NotificationLog, Paginated } from './types'

export function listConfigs() {
  return client.get<NotificationConfig[]>('/notifications/configs').then((r) => r.data)
}

export function createConfig(payload: NotificationConfigCreate) {
  return client.post<NotificationConfig>('/notifications/configs', payload).then((r) => r.data)
}

export function updateConfig(id: number, payload: Partial<NotificationConfigCreate>) {
  return client.put<NotificationConfig>(`/notifications/configs/${id}`, payload).then((r) => r.data)
}

export function deleteConfig(id: number) {
  return client.delete(`/notifications/configs/${id}`).then((r) => r.data)
}

export function testConfig(id: number) {
  return client.post(`/notifications/configs/${id}/test`).then((r) => r.data)
}

export interface NotifLogsQuery {
  limit?: number
  offset?: number
  config_id?: number
  status?: string
}

export function listLogs(params: NotifLogsQuery = {}) {
  return client.get<Paginated<NotificationLog>>('/notifications/logs', { params }).then((r) => r.data)
}
