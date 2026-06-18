import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '监控中心' } },
  { path: '/tasks', name: 'tasks', component: () => import('@/views/TasksView.vue'), meta: { title: '任务注册' } },
  { path: '/schedules', name: 'schedules', component: () => import('@/views/SchedulesView.vue'), meta: { title: '定时调度' } },
  { path: '/data-sync', name: 'data-sync', component: () => import('@/views/DataSyncView.vue'), meta: { title: '数据同步' } },
  { path: '/logs', name: 'logs', component: () => import('@/views/LogsView.vue'), meta: { title: '执行日志' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
