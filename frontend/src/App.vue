<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import { useSocket } from '@/composables/useSocket'
import { useStatsStore } from '@/stores/stats'
import { Monitor, Cpu, Calendar, Document, Sunny, Moon } from '@element-plus/icons-vue'

const socket = useSocket()
const stats = useStatsStore()

const isDark = ref(false)

function toggleTheme() {
  isDark.value = !isDark.value
  if (isDark.value) {
    document.documentElement.classList.add('dark')
    localStorage.setItem('theme', 'dark')
  } else {
    document.documentElement.classList.remove('dark')
    localStorage.setItem('theme', 'light')
  }
}

onMounted(() => {
  socket.on('stats_update', (payload: any) => stats.apply(payload))
  socket.on('new_log', (log: any) => stats.pushLog(log))
  // 初次拉一次
  stats.fetch()

  // Initialize theme
  const savedTheme = localStorage.getItem('theme')
  if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    isDark.value = true
    document.documentElement.classList.add('dark')
  } else {
    isDark.value = false
    document.documentElement.classList.remove('dark')
  }
})
</script>

<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <div class="brand">一科任务调度</div>
      <RouterLink class="nav-item" to="/dashboard">
        <el-icon><Monitor /></el-icon>
        <span>监控中心</span>
      </RouterLink>
      <RouterLink class="nav-item" to="/tasks">
        <el-icon><Cpu /></el-icon>
        <span>任务管理</span>
      </RouterLink>
      <RouterLink class="nav-item" to="/schedules">
        <el-icon><Calendar /></el-icon>
        <span>定时调度</span>
      </RouterLink>
      <RouterLink class="nav-item" to="/logs">
        <el-icon><Document /></el-icon>
        <span>执行日志</span>
      </RouterLink>
      <div class="sidebar-footer">
        <button class="theme-toggle" @click="toggleTheme">
          <el-icon v-if="isDark"><Sunny /></el-icon>
          <el-icon v-else><Moon /></el-icon>
          <span>{{ isDark ? '浅色' : '深色' }}</span>
        </button>
      </div>
    </aside>
    <main class="app-main">
      <RouterView v-slot="{ Component }">
        <transition name="fade-slide" mode="out-in">
          <component :is="Component" />
        </transition>
      </RouterView>
    </main>
  </div>
</template>

