<!--
  SchedulesView — 定时调度管理
  - 列表 (含 next_run_time 倒计时)
  - 新建 (interval / cron, 用 TaskPicker + ParamForm + CronInput)
  - 启停 / 删除
  - schedule_changed socket 事件 → 局部刷新
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useSchedulesStore } from '@/stores/schedules'
import { useTasksStore } from '@/stores/tasks'
import { useSocketListener } from '@/composables/useSocket'
import ScheduleDialog from '@/components/ScheduleDialog.vue'
import { formatDateTime, timeUntil } from '@/utils/format'
import type { Schedule } from '@/api/types'

const schedules = useSchedulesStore()
const tasks = useTasksStore()

const scheduleDialogRef = ref<InstanceType<typeof ScheduleDialog> | null>(null)

function openCreate() {
  scheduleDialogRef.value?.open()
}

function openEdit(s: Schedule) {
  scheduleDialogRef.value?.open(s)
}

async function toggle(s: Schedule) {
  try {
    await schedules.toggle(s.id)
    ElMessage.success(`${s.enabled ? '已禁用' : '已启用'}调度`)
  } catch (e: any) { ElMessage.error(e.message) }
}

async function remove(s: Schedule) {
  try {
    await ElMessageBox.confirm(`确定删除调度 "${s.name}"?`, '确认', { type: 'warning' })
    await schedules.remove(s.id)
    ElMessage.success('已删除')
  } catch { /* cancel */ }
}

function kindOf(ref: string): string {
  return tasks.byRef(ref)?.kind ?? '?'
}
function nameOf(ref: string): string {
  return tasks.byRef(ref)?.name ?? ref
}

function fmtTrigger(s: Schedule): string {
  if (s.trigger_type === 'interval') {
    let baseStr = 'interval'
    for (const k of ['seconds', 'minutes', 'hours', 'days']) {
      if (s.trigger_args[k]) {
        const units: Record<string, string> = { seconds: '秒', minutes: '分钟', hours: '小时', days: '天' }
        baseStr = `每 ${s.trigger_args[k]} ${units[k]}`
        break
      }
    }
    if (s.trigger_args.start_time && s.trigger_args.end_time) {
      baseStr += ` (${s.trigger_args.start_time}~${s.trigger_args.end_time})`
    }
    return baseStr
  }
  const a = s.trigger_args
  return `cron: ${a.minute || '*'} ${a.hour || '*'} ${a.day || '*'} ${a.month || '*'} ${a.day_of_week || '*'}`
}

// 实时推送: 调度变更后回拉一次
useSocketListener('schedule_changed', () => { schedules.load() })

onMounted(async () => {
  await Promise.all([schedules.load(), tasks.load()])
})
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">定时调度</h2>
    <el-skeleton :loading="schedules.loading && !schedules.items.length" animated :rows="6">
      <template #default>
        <div class="panel">
          <div style="margin-bottom:14px">
            <el-button type="primary" :icon="Plus" @click="openCreate">新建调度</el-button>
          </div>
          <el-empty v-if="!schedules.items.length" description="暂无调度" />
          <el-table v-else :data="schedules.items" v-loading="schedules.loading" size="small">
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column label="任务" min-width="240">
              <template #default="{ row }">
                <el-tag size="small" :type="kindOf(row.task_ref)==='python'?'primary':'success'" style="margin-right:6px">
                  {{ kindOf(row.task_ref) }}
                </el-tag>
                {{ nameOf(row.task_ref) }}
              </template>
            </el-table-column>
            <el-table-column label="触发" min-width="180">
              <template #default="{ row }">{{ fmtTrigger(row) }}</template>
            </el-table-column>
            <el-table-column label="下次运行" min-width="200">
              <template #default="{ row }">
                <template v-if="row.next_run_time">
                  <div>{{ formatDateTime(row.next_run_time) }}</div>
                  <small style="color:var(--el-text-color-secondary)">({{ timeUntil(row.next_run_time) }})</small>
                </template>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-switch :model-value="row.enabled" @change="toggle(row)" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" link @click="openEdit(row)">编辑</el-button>
                <el-button size="small" type="danger" link @click="remove(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>
    </el-skeleton>

    <ScheduleDialog ref="scheduleDialogRef" @saved="schedules.load()" />
  </div>
</template>
