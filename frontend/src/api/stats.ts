import client from './client'
import type { StatsPayload } from './types'

export function getStats() {
  return client.get<StatsPayload>('/stats').then((r) => r.data)
}
