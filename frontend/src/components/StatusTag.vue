<!--
  StatusTag — 任务/日志状态的统一标签。
  把 running/success/failed 等枚举到颜色与中文显示的映射收敛到一处, 各页面复用。
-->
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ status: string }>()

const TYPE: Record<string, 'success' | 'danger' | 'info' | 'warning' | 'primary'> = {
  success: 'success',
  failed: 'danger',
  running: 'info',
  pending: 'warning',
}
const LABEL: Record<string, string> = {
  success: '成功',
  failed: '失败',
  running: '运行中',
  pending: '排队中',
}

const type = computed(() => TYPE[props.status] ?? 'warning')
const label = computed(() => LABEL[props.status] ?? props.status)
</script>

<template>
  <el-tag :type="type" size="small">{{ label }}</el-tag>
</template>
