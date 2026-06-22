<!--
  MetricCard — 指标卡片。Dashboard 与 MetricsView 共用。

  props:
    - label: 卡片名 (e.g. "活跃调度")
    - value: 主数值 (string|number)
    - icon: Element Plus 图标组件
    - variant: 'brand' | 'success' | 'warning' | 'info' | 'danger' (色彩主题)

  视觉:
    - 顶部 2px 渐变色带 (按 variant 着色)
    - 图标采用 soft-tint 圆角方块, 替代旧的纯色填充圆
    - hover 时整卡微微浮起 + 阴影加深
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
  <div :class="['metric-card', variant || 'brand']">
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
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 22px;
  background: var(--cf-surface);
  border: 1px solid var(--cf-border-soft);
  border-radius: var(--cf-radius-lg);
  box-shadow: var(--cf-shadow-sm);
  overflow: hidden;
  transition:
    transform var(--cf-trans),
    box-shadow var(--cf-trans),
    border-color var(--cf-trans);
}
.metric-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--cf-brand), #a855f7);
  opacity: 0.9;
}
.metric-card.success::before { background: linear-gradient(90deg, #10b981, #34d399); }
.metric-card.warning::before { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.metric-card.info::before    { background: linear-gradient(90deg, #0ea5e9, #38bdf8); }
.metric-card.danger::before  { background: linear-gradient(90deg, #ef4444, #f87171); }

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--cf-shadow-md);
  border-color: #dde1ec;
}

.metric-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.metric-label {
  font-size: 12px;
  color: var(--cf-text-muted);
  letter-spacing: 0.4px;
  font-weight: 500;
  text-transform: uppercase;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.metric-value {
  font-size: 26px;
  font-weight: 650;
  color: var(--cf-text);
  letter-spacing: -0.4px;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

/* 图标 — soft tint 圆角方块 */
.metric-icon {
  width: 46px;
  height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  flex-shrink: 0;
  transition: transform var(--cf-trans);
}
.metric-card:hover .metric-icon { transform: scale(1.05) rotate(-3deg); }

.metric-icon.brand   { background: rgba(79, 70, 229, 0.10); color: var(--cf-brand);   }
.metric-icon.success { background: rgba(16, 185, 129, 0.10); color: var(--cf-success); }
.metric-icon.warning { background: rgba(245, 158, 11, 0.10); color: var(--cf-warning); }
.metric-icon.info    { background: rgba(14, 165, 233, 0.10); color: var(--cf-info);    }
.metric-icon.danger  { background: rgba(239, 68, 68, 0.10);  color: var(--cf-danger);  }
</style>
