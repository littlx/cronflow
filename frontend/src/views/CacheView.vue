<!--
  CacheView — 缓存数据查询 (upsert 单条) + 双视图 (JSON / 表格)

  - JSON 视图: 展开 document 整体 (与旧版一致)
  - 表格视图: 按 CacheViewConfig (row_path + columns) 把 document 渲染成分页表
    - 客户端分页 (slice), 因 document 是单条 JSON, 行集合在内存里
    - 类型支持: text / number / datetime / boolean / json
    - 列配置走 /api/cache-views/{collection}, 跨设备共享
-->
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Setting, View, Cpu } from '@element-plus/icons-vue'
import { getLatestCache } from '@/api/cache'
import { getCacheView } from '@/api/cacheViews'
import { triggerTask } from '@/api/tasks'
import { useTasksStore } from '@/stores/tasks'
import { useSocketListener } from '@/composables/useSocket'
import { formatDateTime } from '@/utils/format'
import { formatCellValue, getByPath } from '@/utils/cacheFormat'
import CacheViewConfigDialog from '@/components/CacheViewConfigDialog.vue'
import type { CacheItem, CacheViewConfig } from '@/api/types'

const tasks = useTasksStore()

const collection = ref('')
const current = ref<CacheItem | null>(null)
const loading = ref(false)
const notFound = ref(false)

// 视图模式: 'table' | 'json'
// 默认值会在 onCollectionChange 里按是否有列配置自动选择;
// 用户手动切换后, 在同一 collection 内保持其选择, 但切换 collection
// 时仍按新 collection 是否有配置重新决定。
const mode = ref<'table' | 'json'>('table')
// 标记用户在当前 collection 上是否已显式切换过模式
const modeManuallyPicked = ref(false)

// curl 任务的 target_collection 备选列表
const collectionsFromTasks = () => {
  const set = new Set<string>()
  for (const t of tasks.curl) {
    const c = t.handler_config?.target_collection
    if (c) set.add(c)
  }
  return Array.from(set)
}
const suggestions = ref<string[]>([])

// 关联的 cURL 任务列表
const associatedTasks = computed(() => {
  if (!collection.value) return []
  return tasks.items.filter(t => t.kind === 'curl' && t.handler_config?.target_collection === collection.value)
})

const updatingCache = ref(false)

async function triggerAssociatedTasks() {
  if (!associatedTasks.value.length) return
  updatingCache.value = true
  try {
    await Promise.all(
      associatedTasks.value.map(t => triggerTask(t.ref, {}))
    )
    ElMessage.success(`已成功手动触发 ${associatedTasks.value.length} 个关联任务以更新缓存`)
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    updatingCache.value = false
  }
}

// ---- 列配置 ----
const viewConfig = ref<CacheViewConfig | null>(null)
const configLoading = ref(false)
const configDialogVisible = ref(false)

async function loadViewConfig() {
  if (!collection.value) {
    viewConfig.value = null
    return
  }
  configLoading.value = true
  try {
    viewConfig.value = await getCacheView(collection.value)
  } catch (e: any) {
    // 404 = 尚未配置, 静默
    viewConfig.value = null
  } finally {
    configLoading.value = false
  }
}

// ---- 加载 document ----
async function load() {
  if (!collection.value.trim()) return
  loading.value = true
  notFound.value = false
  current.value = null
  try {
    current.value = await getLatestCache(collection.value.trim())
  } catch (e: any) {
    if ((e?.message || '').includes('没有缓存数据') || (e?.message || '').includes('404')) {
      notFound.value = true
    } else {
      ElMessage.error(e.message)
    }
  } finally {
    loading.value = false
  }
}

async function onCollectionChange() {
  // 切换 collection: 同时拉数据 + 列配置, 然后按是否有配置自动选模式。
  page.value = 1
  modeManuallyPicked.value = false
  await Promise.all([load(), loadViewConfig()])
  mode.value = viewConfig.value ? 'table' : 'json'
}

function pinMode() {
  // 用户主动切换视图模式 → 锁定当前选择, 不再被自动逻辑覆盖。
  modeManuallyPicked.value = true
}

// curl 任务执行成功后会广播 curl_changed, 如果当前 collection 在被刷新自动重拉
useSocketListener('curl_changed', () => {
  if (collection.value) load()
})

onMounted(async () => {
  if (!tasks.items.length) await tasks.load()
  suggestions.value = collectionsFromTasks()
  if (suggestions.value.length) {
    collection.value = suggestions.value[0]
    await onCollectionChange()
  }
})

// ---- 表格视图: 行解析 + 分页 ----
const allRows = computed<unknown[]>(() => {
  if (!current.value || !viewConfig.value) return []
  const doc = current.value.document
  const sub = getByPath(doc, viewConfig.value.row_path || '')
  if (Array.isArray(sub)) return sub
  if (sub == null) return []
  return [sub] // 单对象当一行
})

const page = ref(1)
const pageSize = ref(20)
const total = computed(() => allRows.value.length)
const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return allRows.value.slice(start, start + pageSize.value)
})

watch([() => viewConfig.value, () => current.value], () => {
  // 切换数据/配置后重置分页
  page.value = 1
})

// 列宽 fallback
function colWidth(w?: number | null) {
  return w ? `${w}px` : undefined
}

// 单元格点击 (json 类型 → 弹抽屉)
const jsonDrawerVisible = ref(false)
const jsonDrawerValue = ref<unknown>(null)
const jsonDrawerLabel = ref('')
function showCellJson(value: unknown, label: string) {
  jsonDrawerValue.value = value
  jsonDrawerLabel.value = label
  jsonDrawerVisible.value = true
}

function onConfigSaved(cfg: CacheViewConfig) {
  viewConfig.value = cfg
  // 配置刚保存好, 默认切到表格让用户立刻看到效果
  mode.value = 'table'
  modeManuallyPicked.value = false
}
function onConfigCleared() {
  viewConfig.value = null
  mode.value = 'json'
  modeManuallyPicked.value = false
}
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">缓存数据</h2>
    <div class="panel">
      <div class="toolbar">
        <el-select
          v-model="collection"
          filterable allow-create default-first-option
          placeholder="选择或输入 target_collection"
          style="width:340px"
          @change="onCollectionChange"
        >
          <el-option v-for="c in suggestions" :key="c" :label="c" :value="c" />
        </el-select>

        <el-radio-group v-model="mode" @change="pinMode">
          <el-radio-button value="table">
            <el-icon><View /></el-icon> 表格
          </el-radio-button>
          <el-radio-button value="json">
            <el-icon><View /></el-icon> JSON
          </el-radio-button>
        </el-radio-group>

        <el-button
          :icon="Setting"
          :disabled="!collection || !current"
          @click="configDialogVisible = true"
        >列配置</el-button>
        <el-tooltip
          content="未找到与该缓存表关联的 cURL 任务"
          :disabled="associatedTasks.length > 0 || !collection"
          placement="top"
        >
          <span>
            <el-button
              type="primary"
              :icon="Cpu"
              :disabled="!associatedTasks.length"
              :loading="updatingCache"
              @click="triggerAssociatedTasks"
            >更新缓存</el-button>
          </span>
        </el-tooltip>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>

      <!-- 空态 -->
      <el-empty v-if="!collection" description="选择或输入一个 target_collection 查看缓存" />
      <el-empty v-else-if="notFound" :description="`暂无缓存数据 (collection: ${collection})`" />
      <el-skeleton v-else-if="loading && !current" :rows="6" animated />

      <template v-else-if="current">
        <div class="meta">
          <span>id: <code>{{ current.id }}</code></span>
          <span>collection: <code>{{ current.target_collection }}</code></span>
          <span>更新时间: {{ formatDateTime(current.created_at) }}</span>
          <span v-if="viewConfig && mode === 'table'">
            行根路径: <code>{{ viewConfig.row_path || '(根)' }}</code>
          </span>
          <span v-if="mode === 'table' && viewConfig">
            行数: <b>{{ total }}</b>
          </span>
        </div>

        <!-- 表格视图 -->
        <template v-if="mode === 'table'">
          <el-alert
            v-if="!viewConfig"
            type="info"
            :closable="false"
            style="margin-bottom:12px"
          >
            <template #title>
              该 collection 尚未配置列展示。
              <el-button link type="primary" @click="configDialogVisible = true">
                点此打开列配置
              </el-button>
            </template>
          </el-alert>

          <template v-else-if="viewConfig.columns.length === 0">
            <el-empty description="列配置为空, 请添加至少一列" />
          </template>

          <template v-else-if="!total">
            <el-empty description="按当前 row_path 解析不到任何行" />
          </template>

          <template v-else>
            <el-table :data="pagedRows" size="small" stripe>
              <el-table-column
                v-for="col in viewConfig.columns"
                :key="col.key"
                :label="col.label || col.key"
                :width="colWidth(col.width)"
                :min-width="col.width ? undefined : 120"
                show-overflow-tooltip
              >
                <template #default="{ row }">
                  <template v-if="col.type === 'json'">
                    <el-button
                      link size="small" type="primary"
                      @click="showCellJson(getByPath(row, col.key), col.label || col.key)"
                    >
                      {{ formatCellValue(getByPath(row, col.key), 'json') }}
                    </el-button>
                  </template>
                  <template v-else-if="col.type === 'boolean'">
                    <span
                      class="bool-cell"
                      :class="{
                        ok: getByPath(row, col.key) === true || getByPath(row, col.key) === 1 || getByPath(row, col.key) === '1' || getByPath(row, col.key) === 'true',
                        no: getByPath(row, col.key) === false || getByPath(row, col.key) === 0 || getByPath(row, col.key) === '0' || getByPath(row, col.key) === 'false',
                      }"
                    >
                      {{ formatCellValue(getByPath(row, col.key), 'boolean') }}
                    </span>
                  </template>
                  <template v-else>
                    {{ formatCellValue(getByPath(row, col.key), col.type) }}
                  </template>
                </template>
              </el-table-column>
            </el-table>

            <div class="pager">
              <el-pagination
                :current-page="page"
                :page-size="pageSize"
                :total="total"
                :page-sizes="[10, 20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                @current-change="(p: number) => (page = p)"
                @size-change="(s: number) => { pageSize = s; page = 1 }"
              />
            </div>
          </template>
        </template>

        <!-- JSON 视图 -->
        <pre v-else class="cache-doc">{{ JSON.stringify(current.document, null, 2) }}</pre>
      </template>
    </div>

    <!-- 列配置对话框 -->
    <CacheViewConfigDialog
      v-model="configDialogVisible"
      :collection="collection"
      :document="current?.document"
      :initial-config="viewConfig"
      @saved="onConfigSaved"
      @cleared="onConfigCleared"
    />

    <!-- JSON 单元格抽屉 -->
    <el-drawer
      v-model="jsonDrawerVisible"
      :title="`字段: ${jsonDrawerLabel}`"
      size="520px"
      direction="rtl"
    >
      <pre class="cache-doc">{{ JSON.stringify(jsonDrawerValue, null, 2) }}</pre>
    </el-drawer>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.meta {
  display: flex;
  gap: 18px;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.meta code {
  color: var(--fg);
  background: var(--accents-1);
  border: 1px solid var(--border);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11.5px;
}
.cache-doc {
  background: #000;
  color: #ededed;
  padding: 14px 16px;
  border: 1px solid #1a1a1a;
  border-radius: 8px;
  font-family: 'Geist Mono', 'JetBrains Mono', 'SF Mono', Menlo, monospace;
  font-size: 12.5px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  overflow: auto;
  max-height: 640px;
}
/* 黑底里, 全局 ::selection 是黑底白字, 选中后看不见。
   这里单独覆写: 高亮用浅色背景 + 黑字, 选中范围清晰可见。 */
.cache-doc ::selection,
.cache-doc::selection {
  background: #ffcc00;
  color: #000;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.bool-cell.ok { color: var(--geist-success); font-weight: 600; }
.bool-cell.no { color: var(--geist-error); font-weight: 600; }
</style>
