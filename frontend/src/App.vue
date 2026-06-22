<!--
  App 根组件 — 侧边导航 + 路由视图。
  顶层只做:
  - 接收全局 socket 事件 (stats_update / new_log), 灌入 stats store
  - 初始拉取 stats, 让 dashboard 与日志即时可见
  - 显示 socket 连接状态
-->
<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useSocketConnected, useSocketListener } from '@/composables/useSocket'
import { useStatsStore } from '@/stores/stats'
import { Monitor, Cpu, Calendar, Document, Coin, Bell, DataLine } from '@element-plus/icons-vue'

const stats = useStatsStore()
const connected = useSocketConnected()

useSocketListener('stats_update', (payload: any) => stats.apply(payload))
useSocketListener('new_log', (log: any) => stats.pushLog(log))

onMounted(() => {
  stats.fetch()
})
</script>

<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <div class="brand">CronFlow</div>
      <RouterLink class="nav-item" to="/dashboard">
        <el-icon><Monitor /></el-icon>
        <span>监控中心</span>
      </RouterLink>
      <RouterLink class="nav-item" to="/tasks">
        <el-icon><Cpu /></el-icon>
        <span>任务</span>
      </RouterLink>
      <RouterLink class="nav-item" to="/schedules">
        <el-icon><Calendar /></el-icon>
        <span>定时调度</span>
      </RouterLink>
      <RouterLink class="nav-item" to="/logs">
        <el-icon><Document /></el-icon>
        <span>执行日志</span>
      </RouterLink>
      <RouterLink class="nav-item" to="/cache">
        <el-icon><Coin /></el-icon>
        <span>缓存数据</span>
      </RouterLink>
      <RouterLink class="nav-item" to="/notifications">
        <el-icon><Bell /></el-icon>
        <span>通知</span>
      </RouterLink>
      <RouterLink class="nav-item" to="/metrics">
        <el-icon><DataLine /></el-icon>
        <span>指标</span>
      </RouterLink>
      <div style="flex:1"></div>
      <div style="padding:12px 12px 4px;border-top:1px solid var(--border)">
        <span class="conn-indicator" :class="{ online: connected }">
          <span class="dot"></span>
          {{ connected ? 'WebSocket 已连接' : 'WebSocket 断开' }}
        </span>
      </div>
    </aside>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>
