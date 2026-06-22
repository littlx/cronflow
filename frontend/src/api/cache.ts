import client from './client'
import type { CacheItem, Paginated } from './types'

export function listCache(collection: string, limit = 50, offset = 0) {
  return client
    .get<Paginated<CacheItem>>(`/cache/${encodeURIComponent(collection)}`, {
      params: { limit, offset },
    })
    .then((r) => r.data)
}

/** 获取指定 collection 的最新单条缓存 (upsert 语义下即唯一一条)。 */
export function getLatestCache(collection: string) {
  return client
    .get<CacheItem>(`/cache/${encodeURIComponent(collection)}/latest`)
    .then((r) => r.data)
}
