<!--
  MetricCard — 指标卡片。Dashboard 与未来 MetricsView 共用。

  props:
    - label: 卡片名 (e.g. "活跃调度")
    - value: 主数值 (string|number)
    - icon: Element Plus 图标组件
    - variant: 'brand' | 'success' | 'warning' | 'info' | 'danger' (色彩主题)
-->
<script setup lang="ts">
defineProps<{
  label: string
  value: string | number
  icon?: any
  variant?: 'brand' | 'success' | 'warning' | 'info' | 'danger'
}>()
</script>

<template>
  <div class="metric-card">
    <div class="metric-info">
      <div class="metric-label">{{ label }}</div>
      <div class="metric-value">{{ value }}</div>
    </div>
    <div v-if="icon" :class="['metric-icon', variant || 'brand']">
      <el-icon :size="22"><component :is="icon" /></el-icon>
    </div>
  </div>
</template>

<style scoped>
.metric-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  background: var(--el-bg-color-overlay, #fff);
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
}
.metric-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.metric-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  letter-spacing: 0.5px;
}
.metric-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.metric-icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #fff;
}
.metric-icon.brand   { background: var(--el-color-primary); }
.metric-icon.success { background: var(--el-color-success); }
.metric-icon.warning { background: var(--el-color-warning); }
.metric-icon.info    { background: var(--el-color-info); }
.metric-icon.danger  { background: var(--el-color-danger); }
</style>
