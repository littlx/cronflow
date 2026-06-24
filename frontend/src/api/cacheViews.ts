/**
 * 缓存表格视图配置 API。
 *
 * GET 返回 404 时统一抛 Error('尚未配置'); 调用方按需 catch。
 */
import client from './client'
import type { CacheViewConfig, CacheViewConfigUpsert } from './types'

export function getCacheView(collection: string) {
  return client
    .get<CacheViewConfig>(`/cache-views/${encodeURIComponent(collection)}`)
    .then((r) => r.data)
}

export function upsertCacheView(collection: string, payload: CacheViewConfigUpsert) {
  return client
    .put<CacheViewConfig>(`/cache-views/${encodeURIComponent(collection)}`, payload)
    .then((r) => r.data)
}

export function deleteCacheView(collection: string) {
  return client
    .delete<{ ok: boolean }>(`/cache-views/${encodeURIComponent(collection)}`)
    .then((r) => r.data)
}
