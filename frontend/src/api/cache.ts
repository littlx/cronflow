import client from './client'
import type { CacheItem, Paginated } from './types'

export function listCache(collection: string, limit = 50, offset = 0) {
  return client
    .get<Paginated<CacheItem>>(`/cache/${encodeURIComponent(collection)}`, {
      params: { limit, offset },
    })
    .then((r) => r.data)
}
