import { defineStore } from 'pinia'
import client from '@/api/client'

export interface TaskLogItem {
  id: number
  task_ref: string
  task_name: string
  trigger_type: string
  status: string
  attempt?: number
  started_at: string
  finished_at: string | null
  duration: number | null
  result: string | null
  error: string | null
}

export interface StatsPayload {
  total_tasks: number
  total_schedules: number
  active_schedules: number
  total_runs: number
  success_runs: number
  failed_runs: number
  running_runs: number
  success_rate: number
  system: { cpu_usage: number; memory_usage: number }
  recent_logs: TaskLogItem[]
}

export const useStatsStore = defineStore('stats', {
  state: () => ({
    data: null as StatsPayload | null,
    logs: [] as TaskLogItem[],
  }),
  actions: {
    async fetch() {
      try {
        const { data } = await client.get<StatsPayload>('/stats')
        this.apply(data)
      } catch (e) {
        console.error('fetch stats failed', e)
      }
    },
    apply(payload: StatsPayload) {
      this.data = payload
      this.logs = payload.recent_logs || []
    },
    pushLog(log: TaskLogItem) {
      this.logs.unshift(log)
      if (this.logs.length > 50) this.logs.pop()
    },
  },
  getters: {
    ready: (s) => s.data !== null,
  },
})
