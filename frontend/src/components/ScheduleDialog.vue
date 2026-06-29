<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useSchedulesStore } from '@/stores/schedules'
import { useTasksStore } from '@/stores/tasks'
import TaskPicker from '@/components/TaskPicker.vue'
import ParamForm from '@/components/ParamForm.vue'
import CronInput from '@/components/CronInput.vue'
import type { Schedule } from '@/api/types'

const emit = defineEmits(['saved'])

const schedules = useSchedulesStore()
const tasks = useTasksStore()

const visible = ref(false)
const isEdit = ref(false)
const currentId = ref<number | null>(null)

const enableTimeRange = ref(false)
const timeRange = ref<[string, string]>(['08:00', '17:00'])

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

function open(s?: Schedule) {
  if (s) {
    isEdit.value = true
    currentId.value = s.id
    
    let minutes = 5
    if (s.trigger_type === 'interval') {
      minutes = s.trigger_args.minutes ?? 5
    }

    if (s.trigger_type === 'interval' && s.trigger_args.start_time && s.trigger_args.end_time) {
      enableTimeRange.value = true
      timeRange.value = [s.trigger_args.start_time, s.trigger_args.end_time]
    } else {
      enableTimeRange.value = false
      timeRange.value = ['08:00', '17:00']
    }

    const task_args = s.task_args ? JSON.parse(JSON.stringify(s.task_args)) : {}

    form.value = {
      task_ref: s.task_ref,
      name: s.name,
      trigger_type: s.trigger_type,
      interval_minutes: minutes,
      trigger_args_cron: s.trigger_type === 'cron' ? { ...s.trigger_args } : { minute: '*/5', hour: '*', day: '*', month: '*', day_of_week: '*' },
      task_args,
      enabled: s.enabled,
    }
  } else {
    isEdit.value = false
    currentId.value = null
    enableTimeRange.value = false
    timeRange.value = ['08:00', '17:00']
    form.value = {
      task_ref: '', name: '',
      trigger_type: 'interval',
      interval_minutes: 5,
      trigger_args_cron: { minute: '*/5', hour: '*', day: '*', month: '*', day_of_week: '*' },
      task_args: {},
      enabled: true,
    }
  }
  visible.value = true
}

function nameOf(ref: string): string {
  return tasks.byRef(ref)?.name ?? ref
}

async function submit() {
  if (!form.value.task_ref) { ElMessage.error('请选择任务'); return }
  if (!form.value.name) form.value.name = nameOf(form.value.task_ref)

  const trigger_args = form.value.trigger_type === 'interval'
    ? {
        minutes: form.value.interval_minutes,
        start_time: enableTimeRange.value && timeRange.value ? timeRange.value[0] : null,
        end_time: enableTimeRange.value && timeRange.value ? timeRange.value[1] : null,
      }
    : form.value.trigger_args_cron

  try {
    if (isEdit.value) {
      if (currentId.value === null) return
      await schedules.update(currentId.value, {
        name: form.value.name,
        trigger_type: form.value.trigger_type,
        trigger_args,
        task_args: form.value.task_args,
        enabled: form.value.enabled,
      })
      ElMessage.success('已更新调度')
    } else {
      await schedules.create({
        task_ref: form.value.task_ref,
        name: form.value.name,
        trigger_type: form.value.trigger_type,
        trigger_args,
        task_args: form.value.task_args,
        enabled: form.value.enabled,
      })
      ElMessage.success('已创建调度')
    }
    visible.value = false
    emit('saved')
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

defineExpose({ open })
</script>

<template>
  <el-dialog v-model="visible" :title="isEdit ? '编辑调度' : '新建调度'" width="640px" destroy-on-close>
    <el-form label-width="100px">
      <el-form-item label="任务" required>
        <TaskPicker v-model="form.task_ref" :disabled="isEdit" @update:model-value="form.name = nameOf(form.task_ref)" />
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
      <el-form-item v-if="form.trigger_type === 'interval'" label="限时间段">
        <el-switch v-model="enableTimeRange" active-text="仅在设定时间段内运行" />
      </el-form-item>
      <el-form-item v-if="form.trigger_type === 'interval' && enableTimeRange" label="起止时间" required>
        <el-time-picker
          v-model="timeRange"
          is-range
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          format="HH:mm"
          value-format="HH:mm"
          style="width: 240px"
        />
      </el-form-item>
      <el-form-item v-else-if="form.trigger_type === 'cron'" label="Cron 表达式">
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
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="submit">{{ isEdit ? '保存' : '创建' }}</el-button>
    </template>
  </el-dialog>
</template>
