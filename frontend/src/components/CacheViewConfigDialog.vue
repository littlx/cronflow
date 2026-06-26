<!--
  CacheViewConfigDialog — 缓存表格列配置编辑器

  Props:
    - modelValue: 是否显示
    - collection: 目标 collection 名 (用作上下文展示 + 保存 key)
    - document:   当前 collection 的最新 document (用于自动发现/预览)
    - initialConfig?: 现有配置(若有), 用于编辑模式回显; 否则按 inferRows 预填

  Emits:
    - update:modelValue
    - saved(config): 保存成功
    - cleared():     删除配置
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowUp, ArrowDown, Delete, Plus, Refresh } from '@element-plus/icons-vue'
import { deleteCacheView, upsertCacheView } from '@/api/cacheViews'
import { discoverPaths, formatCellValue, getByPath, inferRows } from '@/utils/cacheFormat'
import type {
  CacheCellType,
  CacheColumnConfig,
  CacheViewConfig,
} from '@/api/types'

interface Props {
  modelValue: boolean
  collection: string
  document: unknown
  initialConfig?: CacheViewConfig | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'saved', config: CacheViewConfig): void
  (e: 'cleared'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const rowPath = ref<string>('')
const columns = ref<CacheColumnConfig[]>([])
const saving = ref(false)
const deleting = ref(false)

const TYPE_OPTIONS: { label: string; value: CacheCellType }[] = [
  { label: '文本', value: 'text' },
  { label: '数字', value: 'number' },
  { label: '时间', value: 'datetime' },
  { label: '布尔', value: 'boolean' },
  { label: 'JSON', value: 'json' },
]

/** 当前推断/选择的行集合(用于自动发现 + 预览) */
const rows = computed<unknown[]>(() => {
  const r = getByPath(props.document, rowPath.value)
  if (Array.isArray(r)) return r
  if (r == null) return []
  return [r]
})

const sampleRow = computed<unknown>(() => rows.value[0] ?? null)

/** 在示例行上发现的字段路径, 给 key 输入框做下拉补全 */
const discovered = computed<string[]>(() => {
  if (sampleRow.value == null) return []
  return discoverPaths(sampleRow.value, 3)
})

const previewRows = computed(() => rows.value.slice(0, 3))

watch(
  () => props.modelValue,
  (open, wasOpen) => {
    // 只在「关 → 开」瞬间初始化表单一次, 避免 dialog 打开期间
    // document/initialConfig 变化(例如 curl_changed 自动刷新)把
    // 用户正在编辑的内容覆盖掉。
    if (!open || wasOpen) return
    if (props.initialConfig) {
      rowPath.value = props.initialConfig.row_path || ''
      columns.value = props.initialConfig.columns.map((c) => ({ ...c }))
    } else {
      const inferred = inferRows(props.document)
      rowPath.value = inferred.rowPath
      // 用首行字段批量预填
      const first = inferred.rows[0]
      const paths = first != null ? discoverPaths(first, 2) : []
      columns.value = paths.slice(0, 8).map((p) => ({
        key: p,
        label: p,
        type: inferType(getByPath(first, p)),
      }))
    }
  },
  { immediate: true }
)

function inferType(value: unknown): CacheCellType {
  if (value == null) return 'text'
  if (typeof value === 'boolean') return 'boolean'
  if (typeof value === 'number') {
    // 大整数当 unix 秒/毫秒看待 → 默认仍当 number, 用户可改
    return 'number'
  }
  if (typeof value === 'string') {
    if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(value)) return 'datetime'
    return 'text'
  }
  if (typeof value === 'object') return 'json'
  return 'text'
}

function addColumn() {
  columns.value.push({ key: '', label: '', type: 'text' })
}

function removeColumn(i: number) {
  columns.value.splice(i, 1)
}

function moveUp(i: number) {
  if (i <= 0) return
  const arr = columns.value
  ;[arr[i - 1], arr[i]] = [arr[i], arr[i - 1]]
}

function moveDown(i: number) {
  const arr = columns.value
  if (i >= arr.length - 1) return
  ;[arr[i + 1], arr[i]] = [arr[i], arr[i + 1]]
}

/** 用「自动检测」按钮一次性把已发现但尚未配置的字段加进来 */
function autoDiscover() {
  const existing = new Set(columns.value.map((c) => c.key))
  const added: CacheColumnConfig[] = []
  for (const p of discovered.value) {
    if (existing.has(p)) continue
    added.push({
      key: p,
      label: p,
      type: inferType(getByPath(sampleRow.value, p)),
    })
  }
  if (!added.length) {
    ElMessage.info('未发现新字段')
    return
  }
  columns.value.push(...added)
  ElMessage.success(`已新增 ${added.length} 列`)
}

function refillFromInfer() {
  const inferred = inferRows(props.document)
  rowPath.value = inferred.rowPath
  ElMessage.success(`已重新推断: row_path = "${rowPath.value || '(根)'}"`)
}

async function save() {
  // 校验
  const cleaned: CacheColumnConfig[] = []
  for (const c of columns.value) {
    const key = (c.key || '').trim()
    if (!key) {
      ElMessage.warning('存在空的列字段, 已忽略')
      continue
    }
    cleaned.push({
      key,
      label: (c.label || '').trim() || key,
      type: c.type || 'text',
      width: c.width ?? undefined,
    })
  }
  if (!cleaned.length) {
    ElMessage.warning('至少配置一列')
    return
  }

  saving.value = true
  try {
    const saved = await upsertCacheView(props.collection, {
      row_path: rowPath.value || '',
      columns: cleaned,
    })
    ElMessage.success('已保存')
    emit('saved', saved)
    visible.value = false
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function clearConfig() {
  try {
    await ElMessageBox.confirm('确定删除该 collection 的列配置吗?', '提示', {
      type: 'warning',
    })
  } catch {
    return
  }
  deleting.value = true
  try {
    await deleteCacheView(props.collection)
    ElMessage.success('已删除')
    emit('cleared')
    visible.value = false
  } catch (e: any) {
    ElMessage.error(e.message || '删除失败')
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="`列配置 · ${collection}`"
    width="900px"
    destroy-on-close
  >
    <div class="cfg-body">
      <!-- 行根路径 -->
      <div class="form-row">
        <label>行根路径</label>
        <el-input
          v-model="rowPath"
          placeholder="留空 = document 自身; 否则填 JSON 路径, 如 data.items"
          clearable
          style="flex:1"
        />
        <el-button :icon="Refresh" @click="refillFromInfer">自动推断</el-button>
        <span class="hint">当前可解析行数: <b>{{ rows.length }}</b></span>
      </div>

      <!-- 列编辑表 -->
      <div class="cols-head">
        <div class="section-title" style="margin:0">列定义</div>
        <div style="display:flex;gap:8px">
          <el-button size="small" :icon="Refresh" @click="autoDiscover">从样本批量发现</el-button>
          <el-button size="small" type="primary" :icon="Plus" @click="addColumn">添加列</el-button>
        </div>
      </div>

      <el-empty v-if="!columns.length" description="尚未配置列, 点击添加列或从样本发现" />
      <div v-else class="table-container">
        <table class="cols-table">
          <thead>
            <tr>
              <th style="width:34%">字段 (key)</th>
              <th style="width:22%">列名 (label)</th>
              <th style="width:18%">类型</th>
              <th style="width:12%">宽度</th>
              <th style="width:14%">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(col, i) in columns" :key="i">
              <td>
                <el-input
                  v-model="col.key"
                  placeholder="选择或输入 JSON 路径"
                  size="small"
                  list="discovered-paths"
                  style="width:100%"
                />
              </td>
              <td>
                <el-input v-model="col.label" size="small" placeholder="表头显示名" />
              </td>
              <td>
                <el-select v-model="col.type" size="small" style="width:100%">
                  <el-option
                    v-for="t in TYPE_OPTIONS"
                    :key="t.value"
                    :label="t.label"
                    :value="t.value"
                  />
                </el-select>
              </td>
              <td>
                <el-input-number
                  v-model="col.width"
                  :min="40" :max="800" :step="20"
                  size="small"
                  controls-position="right"
                  style="width:100%"
                />
              </td>
              <td class="ops">
                <el-button link size="small" :icon="ArrowUp" @click="moveUp(i)" />
                <el-button link size="small" :icon="ArrowDown" @click="moveDown(i)" />
                <el-button link size="small" type="danger" :icon="Delete" @click="removeColumn(i)" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 预览 -->
      <div v-if="columns.length && previewRows.length" class="preview">
        <div class="section-title" style="margin:14px 0 8px">预览 (前 3 行)</div>
        <div class="table-container">
          <table class="cols-table">
            <thead>
              <tr>
                <th v-for="c in columns" :key="c.key">{{ c.label || c.key }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in previewRows" :key="i">
                <td v-for="c in columns" :key="c.key" class="preview-cell">
                  {{ formatCellValue(getByPath(r, c.key), c.type) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <template #footer>
      <div style="display:flex;justify-content:space-between;align-items:center;width:100%">
        <el-button
          v-if="initialConfig"
          type="danger" link
          :loading="deleting"
          @click="clearConfig"
        >删除配置</el-button>
        <span v-else />
        <div style="display:flex;gap:8px">
          <el-button @click="visible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="save">保存</el-button>
        </div>
      </div>
    </template>

    <datalist id="discovered-paths">
      <option v-for="p in discovered" :key="p" :value="p" />
    </datalist>
  </el-dialog>
</template>

<style scoped>
.cfg-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.form-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.form-row label {
  flex: 0 0 80px;
  font-size: 13px;
  color: var(--muted);
}
.form-row .hint {
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
}
.cols-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.table-container {
  max-height: 360px;
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.cols-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
}
.cols-table th,
.cols-table td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}
.cols-table th {
  background: var(--accents-1);
  color: var(--muted);
  font-weight: 500;
  text-align: left;
  position: sticky;
  top: 0;
  z-index: 10;
}
.cols-table tr:last-child td {
  border-bottom: none;
}
.cols-table td.ops {
  text-align: right;
}
.preview-cell {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'Geist Mono', 'JetBrains Mono', 'SF Mono', Menlo, monospace;
}
</style>
