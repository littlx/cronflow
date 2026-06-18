<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import client from '@/api/client'
import { ElMessage, ElMessageBox } from 'element-plus'

interface TaskParam { name: string; type: string; default: any; required: boolean; description?: string }
interface Task {
  ref: string
  kind: string
  name: string
  description: string
  handler_config: any
  parameters: TaskParam[]
  id?: string
  module?: string
}

const tasks = ref<Task[]>([])
const loading = ref(false)
const activeTab = ref<'python' | 'curl'>('python')

// 创建/编辑 curl 任务
const dialogVisible = ref(false)
const editingId = ref<string | null>(null)
const form = ref({
  name: '',
  description: '',
  url: '',
  method: 'GET',
  headers: '{}',
  data: '',
  handler_type: 'PURE_JSON',
  target_collection: '',
})

// 缓存预览
const previewVisible = ref(false)
const previewCollection = ref('')
const previewData = ref<any[]>([])

const pythonTasks = computed(() => tasks.value.filter((t) => t.kind === 'python'))
const curlTasks = computed(() => tasks.value.filter((t) => t.kind === 'curl'))

async function load() {
  loading.value = true
  try {
    const { data } = await client.get<Task[]>('/tasks')
    tasks.value = data
  } finally { loading.value = false }
}

async function trigger(t: Task) {
  try {
    await client.post('/tasks/trigger', { task_ref: t.ref, task_args: {} })
    ElMessage.success(`已触发: ${t.name}`)
  } catch (e: any) { ElMessage.error(e.message) }
}

function resetForm() {
  editingId.value = null
  form.value = { name: '', description: '', url: '', method: 'GET', headers: '{}', data: '', handler_type: 'PURE_JSON', target_collection: '' }
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(t: Task) {
  editingId.value = t.id!
  const cfg = t.handler_config || {}
  form.value = {
    name: t.name,
    description: t.description || '',
    url: cfg.url || '',
    method: cfg.method || 'GET',
    headers: JSON.stringify(cfg.headers || {}, null, 2),
    data: cfg.data ? JSON.stringify(cfg.data, null, 2) : '',
    handler_type: cfg.handler_type || 'PURE_JSON',
    target_collection: cfg.target_collection || '',
  }
  dialogVisible.value = true
}

async function submit() {
  let headers = {}
  try { headers = JSON.parse(form.value.headers || '{}') } catch { ElMessage.error('headers 不是合法 JSON'); return }
  let body: any = null
  if (form.value.data) {
    try { body = JSON.parse(form.value.data) } catch { ElMessage.error('data 不是合法 JSON'); return }
  }
  const payload = {
    name: form.value.name,
    description: form.value.description || null,
    handler_config: {
      url: form.value.url,
      method: form.value.method,
      headers,
      data: body,
      handler_type: form.value.handler_type,
      target_collection: form.value.target_collection,
    },
  }
  try {
    if (editingId.value) {
      await client.put(`/tasks/curl/${editingId.value}`, payload)
      ElMessage.success('已更新')
    } else {
      await client.post('/tasks/curl', payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    load()
  } catch (e: any) { ElMessage.error(e.message) }
}

async function remove(t: Task) {
  try {
    await ElMessageBox.confirm(`删除 cURL 任务 "${t.name}"? 关联调度将自动失效。`, '确认', { type: 'warning' })
    await client.delete(`/tasks/curl/${t.id}`)
    ElMessage.success('已删除')
    load()
  } catch { /* cancel */ }
}

async function preview(t: Task) {
  const col = t.handler_config?.target_collection
  if (!col) { ElMessage.warning('未配置 target_collection'); return }
  previewCollection.value = col
  try {
    const { data } = await client.get(`/cache/${col}`)
    previewData.value = data
    previewVisible.value = true
  } catch (e: any) { ElMessage.error(e.message) }
}

onMounted(load)
</script>

<template>
  <h2 class="page-title">任务</h2>
  <div class="panel">
    <el-tabs v-model="activeTab">
      <el-tab-pane label="Python (代码注册)" name="python">
        <el-empty v-if="!pythonTasks.length" description="暂无 Python 任务 (在 backend/tasks/ 下用 @register_task 装饰函数即可注册)" />
        <el-table v-else :data="pythonTasks" v-loading="loading" size="default">
          <el-table-column prop="name" label="任务名" min-width="160" />
          <el-table-column prop="ref" label="ref" min-width="220" show-overflow-tooltip />
          <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
          <el-table-column label="参数" width="100">
            <template #default="{ row }">{{ row.parameters?.length ?? 0 }} 个</template>
          </el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="trigger(row)">立即执行</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="cURL (表单配置)" name="curl">
        <div style="margin-bottom:12px">
          <el-button type="primary" @click="openCreate">+ 新建 cURL 任务</el-button>
        </div>
        <el-empty v-if="!curlTasks.length" description="暂无 cURL 任务" />
        <el-table v-else :data="curlTasks" v-loading="loading" size="small">
          <el-table-column prop="name" label="名称" min-width="120" />
          <el-table-column label="URL" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">{{ row.handler_config?.url }}</template>
          </el-table-column>
          <el-table-column label="缓存表" width="140">
            <template #default="{ row }">{{ row.handler_config?.target_collection }}</template>
          </el-table-column>
          <el-table-column label="处理" width="120">
            <template #default="{ row }">{{ row.handler_config?.handler_type }}</template>
          </el-table-column>
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="trigger(row)">触发</el-button>
              <el-button size="small" @click="preview(row)">预览缓存</el-button>
              <el-button size="small" @click="openEdit(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </div>

  <el-dialog v-model="dialogVisible" :title="editingId ? '编辑 cURL 任务' : '新建 cURL 任务'" width="600px">
    <el-form label-width="100px">
      <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="描述"><el-input v-model="form.description" /></el-form-item>
      <el-form-item label="URL"><el-input v-model="form.url" placeholder="https://..." /></el-form-item>
      <el-form-item label="方法">
        <el-select v-model="form.method" style="width:120px">
          <el-option v-for="m in ['GET','POST','PUT','DELETE']" :key="m" :label="m" :value="m" />
        </el-select>
      </el-form-item>
      <el-form-item label="缓存表名">
        <el-input v-model="form.target_collection" placeholder="my_api_data" />
      </el-form-item>
      <el-form-item label="处理方式">
        <el-select v-model="form.handler_type" style="width:200px">
          <el-option label="纯JSON" value="PURE_JSON" />
          <el-option label="嵌套data" value="NESTED_DATA" />
          <el-option label="原始响应" value="RAW_RESPONSE" />
        </el-select>
      </el-form-item>
      <el-form-item label="Headers"><el-input v-model="form.headers" type="textarea" :rows="2" /></el-form-item>
      <el-form-item label="Body(JSON)"><el-input v-model="form.data" type="textarea" :rows="3" /></el-form-item>
    </el-form>
    <div style="color:#9aa3b2;font-size:12px;padding:0 12px 8px">
      💡 创建后请到「定时调度」页给该任务配置触发周期 (interval/cron)，否则不会自动执行。
    </div>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="submit">{{ editingId ? '更新' : '创建' }}</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="previewVisible" :title="`缓存预览: ${previewCollection}`" width="720px">
    <el-empty v-if="!previewData.length" description="暂无缓存数据" />
    <div v-else style="max-height:480px;overflow:auto">
      <pre v-for="(d,i) in previewData" :key="i" style="background:#0d1117;padding:10px;border-radius:6px;margin-bottom:8px;font-size:12px">{{ JSON.stringify(d.document, null, 2) }}</pre>
    </div>
  </el-dialog>
</template>
