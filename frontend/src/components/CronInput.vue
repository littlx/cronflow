<!--
  CronInput — Cron 5 字段 + 智能预览。SchedulesView 共用。

  v-model:trigger_args 绑定 {minute, hour, day, month, day_of_week}。
-->
<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ modelValue: Record<string, any> }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: Record<string, any>): void }>()

const args = computed({
  get: () => props.modelValue || {},
  set: (v) => emit('update:modelValue', v),
})

function setField(k: string, v: string) {
  emit('update:modelValue', { ...args.value, [k]: v })
}

const preview = computed(() => {
  const m = args.value.minute || '*'
  const h = args.value.hour || '*'
  const d = args.value.day || '*'
  const mo = args.value.month || '*'
  const w = args.value.day_of_week || '*'
  return explainCron(m, h, d, mo, w)
})

function explainCron(m: string, h: string, d: string, mo: string, w: string): string {
  if (m === '*' && h === '*' && d === '*' && mo === '*' && w === '*') return '每分钟'
  if (m.startsWith('*/') && h === '*' && d === '*' && mo === '*' && w === '*')
    return `每 ${m.slice(2)} 分钟`
  if (m === '0' && h.startsWith('*/') && d === '*' && mo === '*' && w === '*')
    return `每 ${h.slice(2)} 小时`

  let timeStr = ''
  if (m === '*' && h === '*') timeStr = '每小时的每分钟'
  else if (m !== '*' && h === '*') timeStr = `每小时的第 ${m} 分钟`
  else if (m === '*' && h !== '*') timeStr = `每天的 ${h} 时每分钟`
  else timeStr = `${h.padStart(2, '0')}:${m.padStart(2, '0')}`

  let dateStr = ''
  if (d === '*' && mo === '*' && w === '*') dateStr = '每天'
  else if (d !== '*' && mo === '*' && w === '*') dateStr = `每月第 ${d} 号`
  else if (d === '*' && mo === '*' && w !== '*') {
    const weeks: Record<string, string> = { '0':'周日','7':'周日','1':'周一','2':'周二','3':'周三','4':'周四','5':'周五','6':'周六','*':'每天' }
    dateStr = `每周 ${w.split(',').map((x) => weeks[x] || x).join('、')}`
  } else if (d !== '*' && mo !== '*') {
    dateStr = `每年 ${mo}月${d}号`
  } else {
    dateStr = `每年 ${mo}月每天`
  }
  return `${dateStr} ${timeStr} 执行`
}
</script>

<template>
  <div class="cron-input">
    <div class="cron-fields">
      <el-input :model-value="args.minute || ''" placeholder="分 *" style="width:90px" @update:model-value="(v: any) => setField('minute', v)" />
      <el-input :model-value="args.hour || ''" placeholder="时 *" style="width:90px" @update:model-value="(v: any) => setField('hour', v)" />
      <el-input :model-value="args.day || ''" placeholder="日 *" style="width:90px" @update:model-value="(v: any) => setField('day', v)" />
      <el-input :model-value="args.month || ''" placeholder="月 *" style="width:90px" @update:model-value="(v: any) => setField('month', v)" />
      <el-input :model-value="args.day_of_week || ''" placeholder="周 *" style="width:90px" @update:model-value="(v: any) => setField('day_of_week', v)" />
    </div>
    <el-alert :title="`智能预览: ${preview}`" type="info" :closable="false" show-icon style="margin-top:8px" />
  </div>
</template>

<style scoped>
.cron-fields {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
