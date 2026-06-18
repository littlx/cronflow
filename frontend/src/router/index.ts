import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '监控中心' } },
  { path: '/tasks', name: 'tasks', component: () => import('@/views/TasksView.vue'), meta: { title: '任务' } },
  { path: '/schedules', name: 'schedules', component: () => import('@/views/SchedulesView.vue'), meta: { title: '定时调度' } },
  { path: '/logs', name: 'logs', component: () => import('@/views/LogsView.vue'), meta: { title: '执行日志' } },
  // 旧路由保持兼容: /data-sync → /tasks (会话默认进 curl tab)
  { path: '/data-sync', redirect: '/tasks' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
