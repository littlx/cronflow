<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '@/api/client'
import { ElMessage } from 'element-plus'
import { useSocket } from '@/composables/useSocket'

const schedules = ref<any[]>([])
const tasks = ref<any[]>([])
const loading = ref(false)
const dialogVisible = ref(false)

const form = ref<{
  task_id: string
  name: string
  task_type: string
  trigger_type: string
  trigger_args: Record<string, any>
  task_args: Record<string, any>
  enabled: boolean
}>({
  task_id: '',
  name: '',
  task_type: 'python',
  trigger_type: 'interval',
  trigger_args: { minutes: 5 },
  task_args: {},
  enabled: true,
})

const socket = useSocket()

async function load() {
  loading.value = true
  try {
    const [s, t] = await Promise.all([client.get('/schedules'), client.get('/tasks')])
    schedules.value = s.data
    tasks.value = t.data
  } finally { loading.value = false }
}

function useTaskParams() {
  const t = tasks.value.find((x) => x.id === form.value.task_id)
  return t?.parameters ?? []
}

async function submit() {
  if (!form.value.task_id) { ElMessage.error('请选择任务'); return }
  try {
    await client.post('/schedules', form.value)
    ElMessage.success('已创建调度')
    dialogVisible.value = false
    load()
  } catch (e: any) { ElMessage.error(e.message) }
}

async function toggle(s: any) {
  try { await client.post(`/schedules/${s.id}/toggle`); load() }
  catch (e: any) { ElMessage.error(e.message) }
}

async function remove(s: any) {
  try { await client.delete(`/schedules/${s.id}`); ElMessage.success('已删除'); load() }
  catch (e: any) { ElMessage.error(e.message) }
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
      <el-button type="primary" @click="dialogVisible = true">+ 新建调度</el-button>
    </div>
    <el-empty v-if="!schedules.length" description="暂无调度" />
    <el-table v-else :data="schedules" v-loading="loading" size="small">
      <el-table-column prop="name" label="名称" min-width="120" />
      <el-table-column prop="task_id" label="任务" min-width="200" show-overflow-tooltip />
      <el-table-column prop="trigger_type" label="触发" width="90" />
      <el-table-column label="参数" min-width="140">
        <template #default="{ row }">{{ JSON.stringify(row.trigger_args) }}</template>
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

  <el-dialog v-model="dialogVisible" title="新建调度" width="560px">
    <el-form label-width="100px">
      <el-form-item label="任务">
        <el-select v-model="form.task_id" filterable style="width:100%" @change="form.name = tasks.find(t=>t.id===$event)?.name || ''">
          <el-option v-for="t in tasks" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="触发类型">
        <el-radio-group v-model="form.trigger_type">
          <el-radio-button value="interval">间隔</el-radio-button>
          <el-radio-button value="cron">Cron</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="form.trigger_type === 'interval'" label="间隔参数">
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
      <el-form-item label="任务参数" v-if="useTaskParams().length">
        <div v-for="p in useTaskParams()" :key="p.name" style="margin-bottom:8px">
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
