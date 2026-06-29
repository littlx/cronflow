<!--
  App 根组件 — 侧边导航 + 路由视图。
  顶层只做:
  - 接收全局 socket 事件 (stats_update / new_log), 灌入 stats store
  - 初始拉取 stats, 让 dashboard 与日志即时可见
  - 显示 socket 连接状态
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useSocketConnected, useSocketListener } from '@/composables/useSocket'
import { useStatsStore } from '@/stores/stats'
import { Monitor, Cpu, Calendar, Document, Coin, Bell, DataLine, Fold, Expand } from '@element-plus/icons-vue'

const stats = useStatsStore()
const connected = useSocketConnected()
const collapsed = ref(false)

useSocketListener('stats_update', (payload: any) => stats.apply(payload))
useSocketListener('new_log', (log: any) => stats.pushLog(log))

onMounted(() => {
  stats.fetch()
})
</script>

<template>
  <div class="app-shell">
    <aside class="app-sidebar" :class="{ collapsed }">
      <div class="brand">
        <span>CronFlow</span>
      </div>
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
      
      <button class="nav-item toggle-btn" @click="collapsed = !collapsed">
        <el-icon>
          <Fold v-if="!collapsed" />
          <Expand v-else />
        </el-icon>
        <span>收起导航</span>
      </button>

      <div class="sidebar-footer">
        <span class="conn-indicator" :class="{ online: connected }">
          <span class="dot"></span>
          <span>{{ connected ? 'WebSocket 已连接' : 'WebSocket 断开' }}</span>
        </span>
      </div>
    </aside>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-sidebar {
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1), padding 0.3s ease;
}

.app-sidebar.collapsed {
  width: 64px;
  padding: 16px 8px;
}

.app-sidebar.collapsed :deep(.brand) {
  justify-content: center;
  gap: 0;
}

.app-sidebar.collapsed :deep(.brand span) {
  display: none;
}

.app-sidebar.collapsed :deep(.nav-item) {
  justify-content: center;
  padding: 8px 0;
  margin: 4px 0;
}

.app-sidebar.collapsed :deep(.nav-item span) {
  display: none;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: flex-start;
}

.app-sidebar.collapsed .sidebar-footer {
  padding: 12px 0;
  justify-content: center;
}

.app-sidebar.collapsed :deep(.conn-indicator) {
  justify-content: center;
  padding: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
}

.app-sidebar.collapsed :deep(.conn-indicator span:not(.dot)) {
  display: none;
}

.toggle-btn {
  background: transparent;
  cursor: pointer;
  border: none;
  width: 100%;
  text-align: left;
  outline: none;
  font-family: inherit;
  margin-bottom: 8px;
}
</style>
