import { defineStore } from 'pinia'
import * as schedulesApi from '@/api/schedules'
import type { Schedule, ScheduleCreate } from '@/api/types'

export const useSchedulesStore = defineStore('schedules', {
  state: () => ({
    items: [] as Schedule[],
    loading: false,
  }),
  actions: {
    async load() {
      this.loading = true
      try {
        this.items = await schedulesApi.listSchedules()
      } finally {
        this.loading = false
      }
    },
    async create(payload: ScheduleCreate) {
      const s = await schedulesApi.createSchedule(payload)
      this.items.push(s)
      return s
    },
    async update(id: number, payload: Partial<ScheduleCreate>) {
      const s = await schedulesApi.updateSchedule(id, payload)
      const idx = this.items.findIndex((x) => x.id === id)
      if (idx >= 0) this.items.splice(idx, 1, s)
      return s
    },
    async toggle(id: number) {
      const s = await schedulesApi.toggleSchedule(id)
      const idx = this.items.findIndex((x) => x.id === id)
      if (idx >= 0) this.items.splice(idx, 1, s)
      return s
    },
    async remove(id: number) {
      await schedulesApi.deleteSchedule(id)
      this.items = this.items.filter((x) => x.id !== id)
    },
  },
})
