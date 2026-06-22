/**
 * 通用表格 composable — 集成分页 + 加载 + 筛选 + 刷新。
 *
 * 抽象:
 *   const { items, loading, total, page, pageSize, load, refresh } = useTable<T>({
 *     fetcher: (params) => api.list({ ...params, ...filters.value }),
 *     pageSize: 50,
 *   })
 *
 * - fetcher 返回 {items, total} 或 T[] (无分页)
 * - 自动管理 loading
 * - 暴露 refresh() 给外部 (筛选变化时调用)
 */
import { ref, type Ref } from 'vue'
import { usePagination } from './usePagination'

export interface TableFetcherResult<T> {
  items: T[]
  total: number
}

export interface UseTableOptions<T> {
  fetcher: (params: { limit: number; offset: number }) => Promise<TableFetcherResult<T> | T[]>
  pageSize?: number
}

export function useTable<T>(options: UseTableOptions<T>) {
  const items: Ref<T[]> = ref([]) as Ref<T[]>
  const loading = ref(false)
  const pagination = usePagination(options.pageSize ?? 50)

  async function load() {
    loading.value = true
    try {
      const r = await options.fetcher(pagination.params.value)
      if (Array.isArray(r)) {
        items.value = r
        pagination.setTotal(r.length)
      } else {
        items.value = r.items
        pagination.setTotal(r.total)
      }
    } finally {
      loading.value = false
    }
  }

  function refresh() {
    pagination.reset()
    return load()
  }

  function onPageChange(p: number) {
    pagination.onChange(p)
    return load()
  }

  function onPageSizeChange(size: number) {
    pagination.onPageSizeChange(size)
    return load()
  }

  return {
    items,
    loading,
    total: pagination.total,
    page: pagination.page,
    pageSize: pagination.pageSize,
    load,
    refresh,
    onPageChange,
    onPageSizeChange,
  }
}
