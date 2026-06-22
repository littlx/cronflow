import { defineStore } from 'pinia'
import { getStats } from '@/api/stats'
import type { StatsPayload, TaskLog } from '@/api/types'

/**
 * 全局监控数据 store。
 * - fetch(): 主动拉取 (页面初始化/手动刷新)
 * - apply(): 收到 socket stats_update 时刷新
 * - pushLog(): 收到 socket new_log 时插入到 recent_logs 头部 (最多 50 条)
 */
export const useStatsStore = defineStore('stats', {
  state: () => ({
    data: null as StatsPayload | null,
    logs: [] as TaskLog[],
  }),
  actions: {
    async fetch() {
      try {
        const data = await getStats()
        this.apply(data)
      } catch (e) {
        console.error('fetch stats failed', e)
      }
    },
    apply(payload: StatsPayload) {
      this.data = payload
      this.logs = payload.recent_logs || []
    },
    pushLog(log: TaskLog) {
      // 同 id 去重 (后端可能因重试发出多次)
      const idx = this.logs.findIndex((l) => l.id === log.id)
      if (idx >= 0) {
        this.logs.splice(idx, 1, log)
      } else {
        this.logs.unshift(log)
        if (this.logs.length > 50) this.logs.pop()
      }
    },
  },
  getters: {
    ready: (s) => s.data !== null,
  },
})
