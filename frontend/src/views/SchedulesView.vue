<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import client from '@/api/client'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useSocket } from '@/composables/useSocket'

interface Task {
  ref: string
  kind: string
  name: string
  parameters: { name: string; type: string; default: any; required: boolean }[]
}

interface Schedule {
  id: number
  task_ref: string
  name: string
  trigger_type: string
  trigger_args: any
  task_args: any
  enabled: boolean
  next_run_time: string | null
}

const schedules = ref<Schedule[]>([])
const tasks = ref<Task[]>([])
const loading = ref(false)
const dialogVisible = ref(false)

const form = ref<{
  task_ref: string
  name: string
  trigger_type: string
  trigger_args: Record<string, any>
  task_args: Record<string, any>
  enabled: boolean
}>({
  task_ref: '',
  name: '',
  trigger_type: 'interval',
  trigger_args: { minutes: 5 },
  task_args: {},
  enabled: true,
})

const socket = useSocket()

const selectedTask = computed(() => tasks.value.find((t) => t.ref === form.value.task_ref))

function kindOf(ref: string): string {
  return tasks.value.find((t) => t.ref === ref)?.kind ?? '?'
}

function nameOf(ref: string): string {
  return tasks.value.find((t) => t.ref === ref)?.name ?? ref
}

async function load() {
  loading.value = true
  try {
    const [s, t] = await Promise.all([client.get('/schedules'), client.get('/tasks')])
    schedules.value = s.data
    tasks.value = t.data
  } finally { loading.value = false }
}

function openCreate() {
  form.value = { task_ref: '', name: '', trigger_type: 'interval', trigger_args: { minutes: 5 }, task_args: {}, enabled: true }
  dialogVisible.value = true
}

async function submit() {
  if (!form.value.task_ref) { ElMessage.error('请选择任务'); return }
  if (!form.value.name) form.value.name = selectedTask.value?.name ?? form.value.task_ref
  try {
    await client.post('/schedules', form.value)
    ElMessage.success('已创建调度')
    dialogVisible.value = false
    load()
  } catch (e: any) { ElMessage.error(e.message) }
}

async function toggle(s: Schedule) {
  try { await client.post(`/schedules/${s.id}/toggle`); load() }
  catch (e: any) { ElMessage.error(e.message) }
}

async function remove(s: Schedule) {
  try {
    await ElMessageBox.confirm(`删除调度 "${s.name}"?`, '确认', { type: 'warning' })
    await client.delete(`/schedules/${s.id}`)
    ElMessage.success('已删除')
    load()
  } catch { /* cancel */ }
}

function fmtTrigger(s: Schedule): string {
  if (s.trigger_type === 'interval') {
    for (const k of ['seconds', 'minutes', 'hours', 'days']) {
      if (s.trigger_args[k]) return `每 ${s.trigger_args[k]} ${k}`
    }
    return 'interval'
  }
  const a = s.trigger_args
  return `cron: ${a.minute || '*'} ${a.hour || '*'} ${a.day || '*'} ${a.month || '*'} ${a.day_of_week || '*'}`
}

onMounted(() => {
  load()
  socket.on('schedule_changed', () => load())
})
</script>

<template>
  <h2 class="page-title">定时调度</h2>
  <div class="panel">
    <div style="margin-bottom:12px">
      <el-button type="primary" @click="openCreate">+ 新建调度</el-button>
    </div>
    <el-empty v-if="!schedules.length" description="暂无调度" />
    <el-table v-else :data="schedules" v-loading="loading" size="small">
      <el-table-column prop="name" label="名称" min-width="120" />
      <el-table-column label="任务" min-width="220">
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
      <el-table-column prop="next_run_time" label="下次运行" min-width="180" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.enabled?'success':'info'" size="small">{{ row.enabled ? '启用' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="toggle(row)">{{ row.enabled ? '禁用' : '启用' }}</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>

  <el-dialog v-model="dialogVisible" title="新建调度" width="600px">
    <el-form label-width="100px">
      <el-form-item label="任务">
        <el-select v-model="form.task_ref" filterable placeholder="选择任意 python / curl 任务" style="width:100%"
                   @change="form.name = nameOf(form.task_ref)">
          <el-option-group label="Python (代码注册)">
            <el-option v-for="t in tasks.filter(x=>x.kind==='python')" :key="t.ref" :label="t.name" :value="t.ref" />
          </el-option-group>
          <el-option-group label="cURL (表单配置)">
            <el-option v-for="t in tasks.filter(x=>x.kind==='curl')" :key="t.ref" :label="t.name" :value="t.ref" />
          </el-option-group>
        </el-select>
      </el-form-item>
      <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="触发类型">
        <el-radio-group v-model="form.trigger_type">
          <el-radio-button value="interval">间隔</el-radio-button>
          <el-radio-button value="cron">Cron</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="form.trigger_type === 'interval'" label="间隔">
        <el-input-number v-model="form.trigger_args.minutes" :min="1" /> 分钟
      </el-form-item>
      <el-form-item v-else label="Cron 参数">
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <el-input v-model="form.trigger_args.minute" placeholder="分 *" style="width:80px" />
          <el-input v-model="form.trigger_args.hour" placeholder="时 *" style="width:80px" />
          <el-input v-model="form.trigger_args.day" placeholder="日 *" style="width:80px" />
          <el-input v-model="form.trigger_args.month" placeholder="月 *" style="width:80px" />
          <el-input v-model="form.trigger_args.day_of_week" placeholder="周 *" style="width:80px" />
        </div>
      </el-form-item>
      <el-form-item v-if="selectedTask?.kind==='python' && selectedTask.parameters.length" label="任务参数">
        <div v-for="p in selectedTask.parameters" :key="p.name" style="margin-bottom:8px">
          <el-input v-model="form.task_args[p.name]" :placeholder="`${p.name} (${p.type})${p.required?' *必填':''}`" />
        </div>
      </el-form-item>
      <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="submit">创建</el-button>
    </template>
  </el-dialog>
</template>
