import client from './client'
import type { Paginated, TaskLog } from './types'

export interface LogsQuery {
  limit?: number
  offset?: number
  task_ref?: string
  status?: string
  started_after?: string
  started_before?: string
}

export function listLogs(params: LogsQuery = {}) {
  return client.get<Paginated<TaskLog>>('/logs', { params }).then((r) => r.data)
}

export function clearLogs() {
  return client.post('/logs/clear').then((r) => r.data)
}
