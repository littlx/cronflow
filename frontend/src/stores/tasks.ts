import { defineStore } from 'pinia'
import * as tasksApi from '@/api/tasks'
import type { Task, CurlTaskCreate } from '@/api/types'

/**
 * 任务列表 store — python (注册表) + curl (DB) 统一视图。
 */
export const useTasksStore = defineStore('tasks', {
  state: () => ({
    items: [] as Task[],
    loading: false,
  }),
  actions: {
    async load() {
      this.loading = true
      try {
        this.items = await tasksApi.listTasks()
      } finally {
        this.loading = false
      }
    },
    async createCurl(payload: CurlTaskCreate) {
      const t = await tasksApi.createCurlTask(payload)
      this.items.push(t)
      return t
    },
    async updateCurl(id: string, payload: Partial<CurlTaskCreate>) {
      const t = await tasksApi.updateCurlTask(id, payload)
      const idx = this.items.findIndex((x) => x.id === id)
      if (idx >= 0) this.items.splice(idx, 1, t)
      return t
    },
    async deleteCurl(id: string) {
      await tasksApi.deleteCurlTask(id)
      this.items = this.items.filter((x) => x.id !== id)
    },
  },
  getters: {
    python: (s) => s.items.filter((t) => t.kind === 'python'),
    curl: (s) => s.items.filter((t) => t.kind === 'curl'),
    byRef: (s) => (ref: string) => s.items.find((t) => t.ref === ref),
  },
})
