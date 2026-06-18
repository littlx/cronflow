<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import client from '@/api/client'
import { ElMessage, ElMessageBox } from 'element-plus'
import { parseCurl } from '@/utils/curl'

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

// 从 curl 命令导入
const curlInput = ref('')
const importVisible = ref(false)
const curlPlaceholder = "curl 'https://api.example.com/data' -H 'Authorization: Bearer xxx' -H 'Content-Type: application/json' -d '{\"key\":\"value\"}'"

const pythonTasks = computed(() => tasks.value.filter((t) => t.kind === 'python'))
const curlTasks = computed(() => tasks.value.filter((t) => t.kind === 'curl'))

const triggerDialogVisible = ref(false)
const selectedTriggerTask = ref<Task | null>(null)
const triggerArgs = ref<Record<string, any>>({})

async function load() {
  loading.value = true
  try {
    const { data } = await client.get<Task[]>('/tasks')
    tasks.value = data
  } finally { loading.value = false }
}

async function trigger(t: Task) {
  if (!t.parameters || t.parameters.length === 0) {
    executeTrigger(t, {})
    return
  }
  selectedTriggerTask.value = t
  triggerArgs.value = {}
  t.parameters.forEach((p) => {
    triggerArgs.value[p.name] = p.default !== undefined ? p.default : ''
  })
  triggerDialogVisible.value = true
}

async function submitTrigger() {
  if (!selectedTriggerTask.value) return
  const args: Record<string, any> = {}
  for (const p of selectedTriggerTask.value.parameters) {
    const val = triggerArgs.value[p.name]
    if (p.required && (val === undefined || val === null || val === '')) {
      ElMessage.error(`参数 ${p.name} 是必填项`)
      return
    }
    if (val !== undefined && val !== null && val !== '') {
      if (p.type === 'int' || p.type === 'integer') {
        args[p.name] = parseInt(val, 10)
        if (isNaN(args[p.name])) {
          ElMessage.error(`参数 ${p.name} 必须是整数`)
          return
        }
      } else if (p.type === 'float' || p.type === 'number') {
        args[p.name] = parseFloat(val)
        if (isNaN(args[p.name])) {
          ElMessage.error(`参数 ${p.name} 必须是数字`)
          return
        }
      } else if (p.type === 'bool' || p.type === 'boolean') {
        args[p.name] = val === true || val === 'true' || val === 1 || val === '1'
      } else {
        args[p.name] = val
      }
    } else if (p.default !== undefined) {
      args[p.name] = p.default
    }
  }

  await executeTrigger(selectedTriggerTask.value, args)
  triggerDialogVisible.value = false
}

async function executeTrigger(t: Task, args: Record<string, any>) {
  try {
    await client.post('/tasks/trigger', { task_ref: t.ref, task_args: args })
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

/** 从 curl 命令导入: 解析后填充表单 (前端解析, 不调后端) */
function importFromCurl() {
  if (!curlInput.value.trim()) {
    ElMessage.warning('请粘贴 curl 命令')
    return
  }
  try {
    const parsed = parseCurl(curlInput.value)

    // 走新建表单流程, 预填解析结果
    editingId.value = null
    form.value = {
      name: '',
      description: '',
      url: parsed.url,
      method: parsed.method,
      headers: JSON.stringify(parsed.headers, null, 2),
      data: parsed.data == null
        ? ''
        : (typeof parsed.data === 'string' ? parsed.data : JSON.stringify(parsed.data, null, 2)),
      handler_type: 'PURE_JSON',
      target_collection: guessCollection(parsed.url),
    }
    importVisible.value = false
    curlInput.value = ''
    dialogVisible.value = true
    ElMessage.success('curl 命令解析成功, 已填充表单')
  } catch (e: any) {
    ElMessage.error('curl 解析失败: ' + (e?.message || String(e)))
  }
}

/** 从 URL host 推断默认 target_collection */
function guessCollection(url: string): string {
  try {
    const host = new URL(url).hostname || ''
    return host.replace(/\./g, '_') || ''
  } catch {
    return ''
  }
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
  <div class="page-container">
    <h2 class="page-title">任务</h2>
    <el-skeleton :loading="loading && !tasks.length" animated :rows="8">
      <template #default>
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
              <div style="margin-bottom:12px;display:flex;gap:8px">
                <el-button type="primary" @click="openCreate">+ 新建 cURL 任务</el-button>
                <el-button @click="importVisible = true">📥 从 curl 命令导入</el-button>
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
      </template>
    </el-skeleton>

    <!-- Parameter Prompt Dialog -->
    <el-dialog v-model="triggerDialogVisible" :title="`立即运行任务: ${selectedTriggerTask?.name}`" width="480px">
      <el-form label-width="120px">
        <div style="margin-bottom: 16px; color: var(--text-secondary); font-size: 13px;">
          请填写任务所需的运行参数：
        </div>
        <el-form-item v-for="p in selectedTriggerTask?.parameters" :key="p.name" :label="p.name" :required="p.required">
          <template v-if="p.type === 'bool' || p.type === 'boolean'">
            <el-switch v-model="triggerArgs[p.name]" />
          </template>
          <template v-else-if="p.type === 'int' || p.type === 'integer' || p.type === 'float' || p.type === 'number'">
            <el-input-number v-model="triggerArgs[p.name]" style="width: 100%" />
          </template>
          <template v-else>
            <el-input v-model="triggerArgs[p.name]" :placeholder="p.description || `类型: ${p.type}`" />
          </template>
          <div v-if="p.description" style="font-size: 11px; color: var(--text-muted); line-height: 1.2; margin-top: 4px;">
            {{ p.description }}
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="triggerDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTrigger">确定运行</el-button>
      </template>
    </el-dialog>

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

    <!-- 从 curl 命令导入 -->
    <el-dialog v-model="importVisible" title="从 curl 命令导入" width="680px">
      <p style="color:var(--text-secondary);font-size:13px;margin-bottom:10px">
        粘贴完整的 curl 命令 (含 URL、-H、-d 等), 解析后自动填充到新建表单。
      </p>
      <el-input
        v-model="curlInput"
        type="textarea"
        :rows="10"
        :placeholder="curlPlaceholder"
        style="font-family:var(--font-mono,monospace);font-size:12px"
      />
      <div style="color:var(--text-muted);font-size:12px;margin-top:8px">
        支持: -X / -H / -d / --data-raw / --data-binary / --json / -A / -b / -e / -u / --compressed 等。
      </div>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" @click="importFromCurl">解析并填充表单</el-button>
      </template>
    </el-dialog>
  </div>
</template>
