<!--
  TasksView — 任务管理
  - python tab: 只读列表 + 立即执行 (参数表单复用 ParamForm)
  - curl tab: CRUD + 从 curl 命令导入 + 立即执行 + 预览缓存
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Upload, QuestionFilled } from '@element-plus/icons-vue'
import { useTasksStore } from '@/stores/tasks'
import { triggerTask } from '@/api/tasks'
import { parseCurl } from '@/utils/curl'
import ParamForm from '@/components/ParamForm.vue'
import type { Task, CacheItem } from '@/api/types'

const tasks = useTasksStore()
const activeTab = ref<'python' | 'curl'>('curl')

// ---- 立即触发参数弹窗 ----
const triggerDlgVisible = ref(false)
const triggerTarget = ref<Task | null>(null)
const triggerArgs = ref<Record<string, any>>({})

function openTrigger(t: Task) {
  if (!t.parameters?.length) {
    executeTrigger(t, {})
    return
  }
  triggerTarget.value = t
  triggerArgs.value = {}
  for (const p of t.parameters) {
    triggerArgs.value[p.name] = p.default ?? ''
  }
  triggerDlgVisible.value = true
}

async function submitTrigger() {
  if (!triggerTarget.value) return
  await executeTrigger(triggerTarget.value, triggerArgs.value)
  triggerDlgVisible.value = false
}

async function executeTrigger(t: Task, args: Record<string, any>) {
  try {
    await triggerTask(t.ref, args)
    ElMessage.success(`已触发: ${t.name}`)
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

// ---- curl 任务 CRUD ----
const curlDlgVisible = ref(false)
const editingId = ref<string | null>(null)

interface CurlForm {
  name: string
  description: string
  url: string
  method: string
  headers: string                 // JSON 文本
  params: string                  // JSON 文本 (query string 键值)
  data: string                    // JSON 文本
  handler_type: 'PURE_JSON' | 'NESTED_DATA' | 'RAW_RESPONSE'
  target_collection: string
  timeout: number | null
}

const emptyForm = (): CurlForm => ({
  name: '', description: '', url: '', method: 'GET',
  headers: '{}', params: '{}', data: '', handler_type: 'PURE_JSON',
  target_collection: '', timeout: null,
})
const curlForm = ref<CurlForm>(emptyForm())

function openCreate() {
  editingId.value = null
  curlForm.value = emptyForm()
  curlDlgVisible.value = true
}

function openEdit(t: Task) {
  editingId.value = t.id!
  const cfg = t.handler_config || {}
  curlForm.value = {
    name: t.name,
    description: t.description || '',
    url: cfg.url || '',
    method: cfg.method || 'GET',
    headers: JSON.stringify(cfg.headers || {}, null, 2),
    params: JSON.stringify(cfg.params || {}, null, 2),
    data: cfg.data ? (typeof cfg.data === 'string' ? cfg.data : JSON.stringify(cfg.data, null, 2)) : '',
    handler_type: cfg.handler_type || 'PURE_JSON',
    target_collection: cfg.target_collection || '',
    timeout: cfg.timeout ?? null,
  }
  curlDlgVisible.value = true
}

async function submitCurl() {
  let headers: Record<string, string> = {}
  try { headers = JSON.parse(curlForm.value.headers || '{}') }
  catch { ElMessage.error('headers 不是合法 JSON'); return }
  let params: Record<string, any> | null = null
  if (curlForm.value.params && curlForm.value.params.trim() && curlForm.value.params.trim() !== '{}') {
    try { params = JSON.parse(curlForm.value.params) }
    catch { ElMessage.error('params 不是合法 JSON'); return }
  }
  let body: any = null
  if (curlForm.value.data) {
    try { body = JSON.parse(curlForm.value.data) }
    catch { body = curlForm.value.data }
  }
  const payload = {
    name: curlForm.value.name,
    description: curlForm.value.description || null,
    handler_config: {
      url: curlForm.value.url,
      method: curlForm.value.method,
      headers,
      params,
      data: body,
      handler_type: curlForm.value.handler_type,
      target_collection: curlForm.value.target_collection,
      timeout: curlForm.value.timeout,
    },
  }
  try {
    if (editingId.value) {
      await tasks.updateCurl(editingId.value, payload as any)
      ElMessage.success('已更新')
    } else {
      await tasks.createCurl(payload as any)
      ElMessage.success('已创建')
    }
    curlDlgVisible.value = false
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

async function removeCurl(t: Task) {
  try {
    await ElMessageBox.confirm(`删除 cURL 任务 "${t.name}"? 关联调度将自动失效。`, '确认', { type: 'warning' })
    await tasks.deleteCurl(t.id!)
    ElMessage.success('已删除')
  } catch { /* 取消 */ }
}

// ---- 从 curl 命令导入 ----
const importDlgVisible = ref(false)
const curlInput = ref('')
const curlPlaceholder = "curl 'https://api.example.com/data' -H 'Authorization: Bearer xxx' -H 'Content-Type: application/json' -d '{\"key\":\"value\"}'"

function guessCollection(url: string): string {
  try {
    const host = new URL(url).hostname || ''
    return host.replace(/\./g, '_') || ''
  } catch { return '' }
}

function importFromCurl() {
  if (!curlInput.value.trim()) {
    ElMessage.warning('请粘贴 curl 命令'); return
  }
  try {
    const p = parseCurl(curlInput.value)
    editingId.value = null
    curlForm.value = {
      name: '', description: '',
      url: p.url, method: p.method,
      headers: JSON.stringify(p.headers, null, 2),
      params: JSON.stringify(p.params || {}, null, 2),
      data: p.data == null ? '' : (typeof p.data === 'string' ? p.data : JSON.stringify(p.data, null, 2)),
      handler_type: 'PURE_JSON',
      target_collection: guessCollection(p.url),
      timeout: null,
    }
    importDlgVisible.value = false
    curlInput.value = ''
    curlDlgVisible.value = true
    ElMessage.success('curl 命令解析成功, 已填充表单')
  } catch (e: any) {
    ElMessage.error('curl 解析失败: ' + (e?.message || String(e)))
  }
}

// ---- 缓存预览 (upsert 语义: 每个 collection 单条最新) ----
const previewVisible = ref(false)
const previewCollection = ref('')
const previewData = ref<CacheItem[]>([])

async function preview(t: Task) {
  const col = t.handler_config?.target_collection
  if (!col) { ElMessage.warning('未配置 target_collection'); return }
  try {
    const { getLatestCache } = await import('@/api/cache')
    const data = await getLatestCache(col)
    previewCollection.value = col
    previewData.value = data ? [data] : []
    previewVisible.value = true
  } catch (e: any) {
    // 404 = 没有缓存数据, 弹窗显示空状态
    if ((e?.message || '').includes('404') || (e?.message || '').includes('没有缓存数据')) {
      previewCollection.value = col
      previewData.value = []
      previewVisible.value = true
    } else {
      ElMessage.error(e.message)
    }
  }
}

onMounted(() => tasks.load())
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">任务</h2>
    <el-skeleton :loading="tasks.loading && !tasks.items.length" animated :rows="6">
      <template #default>
        <div class="panel">
          <el-tabs v-model="activeTab">
            <el-tab-pane label="Python (代码注册)" name="python">
              <el-empty v-if="!tasks.python.length"
                description="暂无 Python 任务 (在 backend/tasks/ 下用 @register_task 装饰函数即可注册)" />
              <el-table v-else :data="tasks.python" v-loading="tasks.loading" size="default">
                <el-table-column prop="name" label="任务名" min-width="160" />
                <el-table-column prop="ref" label="ref" min-width="240" show-overflow-tooltip />
                <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
                <el-table-column label="参数" width="100">
                  <template #default="{ row }">{{ row.parameters?.length ?? 0 }} 个</template>
                </el-table-column>
                <el-table-column label="操作" width="120" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small" type="primary" link @click="openTrigger(row)">立即执行</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <el-tab-pane label="cURL (表单配置)" name="curl">
              <div style="margin-bottom:14px;display:flex;gap:8px">
                <el-button type="primary" :icon="Plus" @click="openCreate">新建 cURL 任务</el-button>
                <el-button :icon="Upload" @click="importDlgVisible = true">从 cURL 导入</el-button>
              </div>
              <el-empty v-if="!tasks.curl.length" description="暂无 cURL 任务" />
              <el-table v-else :data="tasks.curl" v-loading="tasks.loading" size="small">
                <el-table-column prop="name" label="名称" min-width="120" />
                <el-table-column label="URL" min-width="220" show-overflow-tooltip>
                  <template #default="{ row }">{{ row.handler_config?.url }}</template>
                </el-table-column>
                <el-table-column label="缓存表" width="160">
                  <template #default="{ row }">{{ row.handler_config?.target_collection }}</template>
                </el-table-column>
                <el-table-column label="处理" width="120">
                  <template #default="{ row }">{{ row.handler_config?.handler_type }}</template>
                </el-table-column>
                <el-table-column label="操作" width="300" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small" type="primary" link @click="openTrigger(row)">触发</el-button>
                    <el-button size="small" type="primary" link @click="preview(row)">预览缓存</el-button>
                    <el-button size="small" type="primary" link @click="openEdit(row)">编辑</el-button>
                    <el-button size="small" type="danger" link @click="removeCurl(row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
          </el-tabs>
        </div>
      </template>
    </el-skeleton>

    <!-- 触发参数弹窗 -->
    <el-dialog v-model="triggerDlgVisible" :title="`立即运行: ${triggerTarget?.name}`" width="520px" destroy-on-close>
      <ParamForm v-if="triggerTarget" :parameters="triggerTarget.parameters" v-model="triggerArgs" />
      <template #footer>
        <el-button @click="triggerDlgVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTrigger">确定运行</el-button>
      </template>
    </el-dialog>

    <!-- curl 任务编辑/新建 -->
    <el-dialog
      v-model="curlDlgVisible"
      width="960px"
      destroy-on-close
    >
      <template #header>
        <div style="display: flex; align-items: center; gap: 6px;">
          <span style="font-size: 16px; font-weight: 600;">{{ editingId ? '编辑 cURL 任务' : '新建 cURL 任务' }}</span>
          <el-tooltip content="创建后请到「定时调度」页为该任务配置触发周期 (间隔/Cron)，否则不会自动执行。" placement="top" effect="dark">
            <el-icon style="cursor: pointer; color: var(--el-text-color-secondary); font-size: 14px;"><QuestionFilled /></el-icon>
          </el-tooltip>
        </div>
      </template>

      <div class="curl-form-grid">
        <!-- 左栏: 基本信息 -->
        <section class="form-col">
          <div class="form-col-title">基本信息</div>
          <el-form label-width="86px" label-position="left">
            <el-form-item label="名称">
              <el-input v-model="curlForm.name" placeholder="任务名称" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="curlForm.description" placeholder="可选" />
            </el-form-item>
            <el-form-item label="URL">
              <el-input v-model="curlForm.url" placeholder="https://..." />
            </el-form-item>

            <div class="row-2">
              <el-form-item label="方法" label-width="86px">
                <el-select v-model="curlForm.method" style="width:100%">
                  <el-option v-for="m in ['GET','POST','PUT','DELETE','PATCH']" :key="m" :label="m" :value="m" />
                </el-select>
              </el-form-item>
              <el-form-item label="超时(秒)" label-width="86px">
                <el-input-number
                  v-model="curlForm.timeout" :min="1" :max="600"
                  placeholder="默认 60" style="width:100%" controls-position="right"
                />
              </el-form-item>
            </div>

            <el-form-item label="缓存表名">
              <el-input v-model="curlForm.target_collection" placeholder="my_api_data" />
            </el-form-item>
            <el-form-item label="处理方式">
              <el-select v-model="curlForm.handler_type" style="width:100%">
                <el-option label="纯JSON" value="PURE_JSON" />
                <el-option label="嵌套data" value="NESTED_DATA" />
                <el-option label="原始响应" value="RAW_RESPONSE" />
              </el-select>
            </el-form-item>
          </el-form>
        </section>

        <!-- 右栏: Headers + Params + Body -->
        <section class="form-col">
          <div class="form-col-title" style="display: flex; align-items: center; gap: 6px;">
            <span>Headers / Params / Body</span>
            <el-tooltip placement="top" effect="dark">
              <template #content>
                <div v-pre style="font-size:11px;line-height:1.65;max-width:340px">
                  <div style="font-weight:600;margin-bottom:6px;color:var(--el-color-primary-light-3)">支持的动态参数占位符（运行前自动替换）：</div>
                  <div style="margin-bottom:3px">• <code>{{ now }}</code>: 本地当前时间 (如 <code>2026-06-25 16:16:44</code>)</div>
                  <div style="margin-bottom:3px">• <code>{{ now_iso }}</code>: ISO 8601 本地时间 (如 <code>2026-06-25T16:16:44+08:00</code>)</div>
                  <div style="margin-bottom:3px">• <code>{{ today }}</code> / <code>{{ yesterday }}</code> / <code>{{ tomorrow }}</code>: 日期 (如 <code>2026-06-25</code>)</div>
                  <div style="margin-bottom:3px">• <code>{{ timestamp }}</code>: 秒级 Unix 时间戳 (如 <code>1782348555</code>)</div>
                  <div style="margin-bottom:10px">• <code>{{ uuid }}</code>: 随机 UUID 字符串 (如 <code>db6d8ede-e1b4-4b59-bf23...</code>)</div>
                  <div style="font-weight:600;margin-bottom:4px;color:var(--el-color-primary-light-3)">填写配置示例 (JSON)：</div>
                  <pre style="margin:0;background:rgba(255,255,255,0.08);padding:6px;border-radius:4px;font-family:monospace;font-size:10px;color:#ededed;line-height:1.4">{\n  "startTime": "{{ yesterday }} 00:00:00",\n  "endTime": "{{ now }}"\n}</pre>
                </div>
              </template>
              <el-icon style="cursor: pointer; color: var(--el-text-color-secondary); font-size: 13px;"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
          <el-form label-width="0" label-position="top">
            <el-form-item label="Headers (JSON)">
              <el-input
                v-model="curlForm.headers"
                type="textarea" :rows="6"
                placeholder='{"Authorization": "Bearer ..."}'
                class="mono-input"
              />
            </el-form-item>
            <el-form-item label="Params (URL query, JSON)">
              <el-input
                v-model="curlForm.params"
                type="textarea" :rows="5"
                placeholder='{"page": 1, "size": 20}'
                class="mono-input"
              />
            </el-form-item>
            <el-form-item label="Body">
              <el-input
                v-model="curlForm.data"
                type="textarea" :rows="6"
                placeholder="JSON / form / raw"
                class="mono-input"
              />
            </el-form-item>
          </el-form>
        </section>
      </div>

      <template #footer>
        <el-button @click="curlDlgVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCurl">{{ editingId ? '更新' : '创建' }}</el-button>
      </template>
    </el-dialog>

    <!-- 从 curl 命令导入 -->
    <el-dialog v-model="importDlgVisible" title="从 curl 命令导入" width="680px" destroy-on-close>
      <p style="color:var(--el-text-color-secondary);font-size:13px;margin:0 0 10px">
        粘贴完整的 curl 命令 (含 URL、-H、-d 等), 解析后自动填充到新建表单。
      </p>
      <el-input
        v-model="curlInput"
        type="textarea"
        :rows="10"
        :placeholder="curlPlaceholder"
        style="font-family: 'Geist Mono', 'JetBrains Mono', 'SF Mono', Menlo, monospace; font-size:12px"
      />
      <div style="color:var(--el-text-color-secondary);font-size:12px;margin-top:8px">
        支持: -X / -H / -d / --data-raw / --data-binary / --json / -A / -b / -e / -u / --compressed 等。
      </div>
      <template #footer>
        <el-button @click="importDlgVisible = false">取消</el-button>
        <el-button type="primary" @click="importFromCurl">解析并填充</el-button>
      </template>
    </el-dialog>

    <!-- 缓存预览 -->
    <el-dialog v-model="previewVisible" :title="`缓存预览: ${previewCollection}`" width="780px" destroy-on-close>
      <el-empty v-if="!previewData.length" description="暂无缓存数据" />
      <div v-else style="max-height:480px;overflow:auto">
        <pre
          v-for="d in previewData" :key="d.id"
          style="background:#000;color:#ededed;border:1px solid #1a1a1a;padding:12px 14px;border-radius:6px;margin-bottom:8px;font-family:'Geist Mono','JetBrains Mono','SF Mono',Menlo,monospace;font-size:12px;line-height:1.55;white-space:pre-wrap"
        >{{ JSON.stringify(d.document, null, 2) }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
/* curl 表单两栏布局: 左基本信息, 右 Headers/Body */
.curl-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}
.form-col {
  min-width: 0;
}
.form-col-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--muted);
  letter-spacing: 0.02em;
  text-transform: uppercase;
  margin: 0 0 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
/* 同一行并排两个 form-item */
.row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.row-2 :deep(.el-form-item) {
  margin-bottom: 18px;
}
/* 等宽字体的 textarea (Headers/Body) */
.mono-input :deep(.el-textarea__inner) {
  font-family: 'Geist Mono', 'JetBrains Mono', 'SF Mono', Menlo, monospace;
  font-size: 12px;
  line-height: 1.55;
}
/* 窄屏 → 单栏堆叠 */
@media (max-width: 860px) {
  .curl-form-grid { grid-template-columns: 1fr; }
}
</style>
