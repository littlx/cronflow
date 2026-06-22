<!--
  MetricCard — Vercel-style 指标卡片。
  - 无渐变, 无 hover 浮起
  - 单色细边框 + 极简排版
  - 主数值采用大号粗体, label 灰色小字在上方
  - 图标小尺寸放在右上角, 单色描边风
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
    <div class="metric-head">
      <span class="metric-label">{{ label }}</span>
      <el-icon v-if="icon" :class="['metric-icon', variant || 'brand']" :size="14">
        <component :is="icon" />
      </el-icon>
    </div>
    <div class="metric-value">{{ value }}</div>
  </div>
</template>

<style scoped>
.metric-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: border-color var(--duration) var(--ease);
}
.metric-card:hover {
  border-color: var(--border-strong);
}

.metric-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 16px;
}
.metric-label {
  font-size: 12.5px;
  color: var(--muted);
  font-weight: 500;
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.metric-icon {
  color: var(--muted-soft);
  flex-shrink: 0;
}
.metric-icon.success { color: var(--geist-success); }
.metric-icon.warning { color: var(--geist-warning); }
.metric-icon.danger  { color: var(--geist-error); }
.metric-icon.info    { color: var(--muted); }
.metric-icon.brand   { color: var(--fg); }

.metric-value {
  font-size: 30px;
  font-weight: 600;
  line-height: 1.15;
  letter-spacing: -0.03em;
  color: var(--fg);
  font-variant-numeric: tabular-nums;
}
</style>
