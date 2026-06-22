<!--
  SchedulesView — 定时调度管理
  - 列表 (含 next_run_time 倒计时)
  - 新建 (interval / cron, 用 TaskPicker + ParamForm + CronInput)
  - 启停 / 删除
  - schedule_changed socket 事件 → 局部刷新
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useSchedulesStore } from '@/stores/schedules'
import { useTasksStore } from '@/stores/tasks'
import { useSocketListener } from '@/composables/useSocket'
import TaskPicker from '@/components/TaskPicker.vue'
import ParamForm from '@/components/ParamForm.vue'
import CronInput from '@/components/CronInput.vue'
import { formatDateTime, timeUntil } from '@/utils/format'
import type { Schedule } from '@/api/types'

const schedules = useSchedulesStore()
const tasks = useTasksStore()

// 新建表单
const dialogVisible = ref(false)
const form = ref({
  task_ref: '',
  name: '',
  trigger_type: 'interval' as 'interval' | 'cron',
  interval_minutes: 5,
  trigger_args_cron: { minute: '*/5', hour: '*', day: '*', month: '*', day_of_week: '*' } as Record<string, any>,
  task_args: {} as Record<string, any>,
  enabled: true,
})

const selectedTask = computed(() => tasks.byRef(form.value.task_ref))

function openCreate() {
  form.value = {
    task_ref: '', name: '',
    trigger_type: 'interval',
    interval_minutes: 5,
    trigger_args_cron: { minute: '*/5', hour: '*', day: '*', month: '*', day_of_week: '*' },
    task_args: {},
    enabled: true,
  }
  dialogVisible.value = true
}

async function submit() {
  if (!form.value.task_ref) { ElMessage.error('请选择任务'); return }
  if (!form.value.name) form.value.name = selectedTask.value?.name ?? form.value.task_ref

  const trigger_args = form.value.trigger_type === 'interval'
    ? { minutes: form.value.interval_minutes }
    : form.value.trigger_args_cron

  try {
    await schedules.create({
      task_ref: form.value.task_ref,
      name: form.value.name,
      trigger_type: form.value.trigger_type,
      trigger_args,
      task_args: form.value.task_args,
      enabled: form.value.enabled,
    })
    ElMessage.success('已创建调度')
    dialogVisible.value = false
  } catch (e: any) {
    ElMessage.error(e.message)
  }
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
    for (const k of ['seconds', 'minutes', 'hours', 'days']) {
      if (s.trigger_args[k]) {
        const units: Record<string, string> = { seconds: '秒', minutes: '分钟', hours: '小时', days: '天' }
        return `每 ${s.trigger_args[k]} ${units[k]}`
      }
    }
    return 'interval'
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
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="danger" link @click="remove(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>
    </el-skeleton>

    <el-dialog v-model="dialogVisible" title="新建调度" width="640px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="任务" required>
          <TaskPicker v-model="form.task_ref" @update:model-value="form.name = nameOf(form.task_ref)" />
        </el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" placeholder="不填则用任务名" /></el-form-item>
        <el-form-item label="触发类型">
          <el-radio-group v-model="form.trigger_type">
            <el-radio-button value="interval">间隔</el-radio-button>
            <el-radio-button value="cron">Cron</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.trigger_type === 'interval'" label="间隔">
          <el-input-number v-model="form.interval_minutes" :min="1" /> 分钟
        </el-form-item>
        <el-form-item v-else label="Cron 表达式">
          <CronInput v-model="form.trigger_args_cron" />
        </el-form-item>
        <el-form-item
          v-if="selectedTask?.kind === 'python' && selectedTask.parameters.length"
          label="任务参数"
        >
          <ParamForm :parameters="selectedTask.parameters" v-model="form.task_args" />
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>
