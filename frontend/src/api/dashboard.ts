/**
 * 监控中心看板展示配置 API。
 */
import client from './client'
import type { DashboardConfig, DashboardConfigUpsert } from './types'

export function getDashboardConfig() {
  return client
    .get<DashboardConfig>('/dashboard/config')
    .then((r) => r.data)
}

export function upsertDashboardConfig(payload: DashboardConfigUpsert) {
  return client
    .put<DashboardConfig>('/dashboard/config', payload)
    .then((r) => r.data)
}
