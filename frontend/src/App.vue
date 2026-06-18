<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useSocket } from '@/composables/useSocket'
import { useStatsStore } from '@/stores/stats'

const socket = useSocket()
const stats = useStatsStore()

onMounted(() => {
  socket.on('stats_update', (payload: any) => stats.apply(payload))
  socket.on('new_log', (log: any) => stats.pushLog(log))
  // 初次拉一次
  stats.fetch()
})
</script>

<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <div class="brand">CronFlow v2</div>
      <RouterLink class="nav-item" to="/dashboard">监控中心</RouterLink>
      <RouterLink class="nav-item" to="/tasks">任务</RouterLink>
      <RouterLink class="nav-item" to="/schedules">定时调度</RouterLink>
      <RouterLink class="nav-item" to="/logs">执行日志</RouterLink>
    </aside>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
