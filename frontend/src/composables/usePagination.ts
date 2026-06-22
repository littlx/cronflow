/**
 * 分页 composable — 所有列表页通用。
 *
 * 设计目标:
 * - 把 page/pageSize/total/offset 这些状态收敛到一处
 * - 与 Element Plus 的 el-pagination 通过 currentPage/pageSize 直接对接
 * - 翻页/改页大小/重置 时统一调用外部 fetcher
 *
 * 使用:
 *   const { page, pageSize, total, params, onChange, reset } = usePagination(50)
 *   // params.value -> { limit, offset }, 传给 API
 *   watch([page, pageSize, ...filters], () => load())
 */
import { computed, ref } from 'vue'

export function usePagination(initialPageSize = 50) {
  const page = ref(1)
  const pageSize = ref(initialPageSize)
  const total = ref(0)

  const params = computed(() => ({
    limit: pageSize.value,
    offset: (page.value - 1) * pageSize.value,
  }))

  function onChange(p: number) {
    page.value = p
  }

  function onPageSizeChange(size: number) {
    pageSize.value = size
    page.value = 1
  }

  function reset() {
    page.value = 1
  }

  function setTotal(n: number) {
    total.value = n
  }

  return { page, pageSize, total, params, onChange, onPageSizeChange, reset, setTotal }
}
