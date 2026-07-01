<!--
  DashboardView — 监控中心
  - 4 个指标卡片 (复用 MetricCard)
  - 最近日志表格 (复用 LogTerminal 详情)

  数据全部来自 useStatsStore (全局 socket + 初始 fetch), 本组件无独立请求。
-->
<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { Setting, ArrowRight, Cpu, Refresh, Plus, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useStatsStore } from '@/stores/stats'
import { useTasksStore } from '@/stores/tasks'
import { useSchedulesStore } from '@/stores/schedules'
import { useSocketListener } from '@/composables/useSocket'
import { listLogs } from '@/api/logs'
import { getCacheView } from '@/api/cacheViews'
import { getLatestCache } from '@/api/cache'
import { triggerTask } from '@/api/tasks'
import { getDashboardConfig, upsertDashboardConfig } from '@/api/dashboard'
import { getByPath, formatCellValue } from '@/utils/cacheFormat'
import StatusTag from '@/components/StatusTag.vue'
import LogTerminal from '@/components/LogTerminal.vue'
import ScheduleDialog from '@/components/ScheduleDialog.vue'
import type { TaskLog, CacheViewConfig } from '@/api/types'
import { formatDateTime, formatDuration, timeUntil } from '@/utils/format'

const stats = useStatsStore()
const tasks = useTasksStore()
const schedules = useSchedulesStore()

const terminalVisible = ref(false)
const selectedLog = ref<TaskLog | null>(null)
function showDetail(row: TaskLog) {
  selectedLog.value = row
  terminalVisible.value = true
}

function triggerLabel(t: string) {
  return { interval: '间隔', cron: 'Cron', manual: '手动' }[t] || t
}

function nameOf(ref: string): string {
  return tasks.byRef(ref)?.name ?? ref
}

function fmtTrigger(s: any): string {
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

async function toggleSchedule(s: any) {
  try {
    await schedules.toggle(s.id)
    ElMessage.success(`${s.enabled ? '已禁用' : '已启用'}调度`)
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

// --- 任务调度/日志 无限滚动 (鼠标滚动获取下一页) ---
const logsList = ref<TaskLog[]>([])
const logsLimit = 20
const logsOffset = ref(0)
const logsLoading = ref(false)
const logsHasMore = ref(true)

async function loadNextLogsPage() {
  if (logsLoading.value || !logsHasMore.value) return
  logsLoading.value = true
  try {
    const data = await listLogs({
      limit: logsLimit,
      offset: logsOffset.value
    })
    const items = data.items || []
    if (items.length < logsLimit) {
      logsHasMore.value = false
    }
    if (logsOffset.value === 0) {
      logsList.value = items
    } else {
      logsList.value.push(...items)
    }
    logsOffset.value += items.length
  } catch (e: any) {
    console.error('Failed to load logs', e)
  } finally {
    logsLoading.value = false
  }
}

function resetLogs() {
  logsList.value = []
  logsOffset.value = 0
  logsHasMore.value = true
  loadNextLogsPage()
}

const schedulesLimit = 20
const schedulesVisibleCount = ref(20)

const visibleSchedules = computed(() => {
  return schedules.items.slice(0, schedulesVisibleCount.value)
})

const schedulesHasMore = computed(() => {
  return schedulesVisibleCount.value < schedules.items.length
})

function loadNextSchedulesPage() {
  if (schedulesHasMore.value) {
    schedulesVisibleCount.value += schedulesLimit
  }
}

watch(() => schedules.items, () => {
  if (schedulesVisibleCount.value < 20) {
    schedulesVisibleCount.value = 20
  }
})

const logsTableRef = ref<any>(null)
const schedulesTableRef = ref<any>(null)

function attachScrollListeners() {
  if (logsTableRef.value) {
    const scrollEl = logsTableRef.value.$el.querySelector('.el-scrollbar__wrap')
    if (scrollEl && !scrollEl._scrollListenerAttached) {
      scrollEl.addEventListener('scroll', () => {
        if (scrollEl.scrollHeight - scrollEl.scrollTop <= scrollEl.clientHeight + 20) {
          loadNextLogsPage()
        }
      })
      scrollEl._scrollListenerAttached = true
    }
  }
  if (schedulesTableRef.value) {
    const scrollEl = schedulesTableRef.value.$el.querySelector('.el-scrollbar__wrap')
    if (scrollEl && !scrollEl._scrollListenerAttached) {
      scrollEl.addEventListener('scroll', () => {
        if (scrollEl.scrollHeight - scrollEl.scrollTop <= scrollEl.clientHeight + 20) {
          loadNextSchedulesPage()
        }
      })
      scrollEl._scrollListenerAttached = true
    }
  }
}

// --- 新建/编辑/删除 调度管理 ---
const scheduleDialogRef = ref<InstanceType<typeof ScheduleDialog> | null>(null)

function openCreate() {
  scheduleDialogRef.value?.open()
}

function openEdit(s: any) {
  scheduleDialogRef.value?.open(s)
}

async function removeSchedule(s: any) {
  try {
    await ElMessageBox.confirm(`确定删除调度 "${s.name}"?`, '确认', { type: 'warning' })
    await schedules.remove(s.id)
    ElMessage.success('已删除')
    schedules.load()
  } catch { /* cancel */ }
}

// ---- 缓存数据展示选择 ----
const settingsVisible = ref(false)
const activeConfigCol = ref<string | null>(null)

interface AlertRule {
  column: string
  operator: 'eq' | 'ne' | 'contains' | 'gt' | 'lt' | 'is_today'
  value: string
}

interface DashboardTableConfig {
  collection: string
  width: 'third' | 'half' | 'full'
  visibleColumns: string[]
  sortBy?: string | null
  sortOrder?: 'asc' | 'desc' | null
  alertRules?: AlertRule[]
}

const chosenTables = ref<DashboardTableConfig[]>([])

const allCollections = computed(() => {
  const set = new Set<string>()
  for (const t of tasks.curl) {
    const c = t.handler_config?.target_collection
    if (c) set.add(c)
  }
  return Array.from(set)
})

const sidebarCollections = computed(() => {
  const orderedList: string[] = []
  const set = new Set<string>()
  for (const t of chosenTables.value) {
    if (!set.has(t.collection)) {
      set.add(t.collection)
      orderedList.push(t.collection)
    }
  }
  for (const col of allCollections.value) {
    if (!set.has(col)) {
      set.add(col)
      orderedList.push(col)
    }
  }
  return orderedList
})

const dragIndex = ref<number | null>(null)
const dragOverIndex = ref<number | null>(null)

function onDragStart(index: number) {
  dragIndex.value = index
}

function onDragOver(event: DragEvent) {
  event.preventDefault()
}

function onDragEnter(index: number) {
  dragOverIndex.value = index
}

function onDragLeave() {
  dragOverIndex.value = null
}

function onDrop(index: number) {
  if (dragIndex.value === null || dragIndex.value === index) {
    dragIndex.value = null
    dragOverIndex.value = null
    return
  }
  
  const dragCol = sidebarCollections.value[dragIndex.value]
  const targetCol = sidebarCollections.value[index]
  
  const dragIdxInChosen = chosenTables.value.findIndex(t => t.collection === dragCol)
  const targetIdxInChosen = chosenTables.value.findIndex(t => t.collection === targetCol)
  
  if (dragIdxInChosen !== -1 && targetIdxInChosen !== -1) {
    const arr = [...chosenTables.value]
    const [removed] = arr.splice(dragIdxInChosen, 1)
    arr.splice(targetIdxInChosen, 0, removed)
    chosenTables.value = arr
  }
  
  dragIndex.value = null
  dragOverIndex.value = null
}

interface CacheTableData {
  collection: string
  loading: boolean
  notFound: boolean
  viewConfig: CacheViewConfig | null
  rows: any[]
  createdAt: string | null
  triggerLoading: boolean
}
const cacheTables = ref<Record<string, CacheTableData>>({})

async function loadCacheTableData(col: string) {
  if (!cacheTables.value[col]) {
    cacheTables.value[col] = {
      collection: col,
      loading: true,
      notFound: false,
      viewConfig: null,
      rows: [],
      createdAt: null,
      triggerLoading: false
    }
  }
  const item = cacheTables.value[col]
  item.loading = true
  item.notFound = false
  try {
    const [cfg, cache] = await Promise.all([
      getCacheView(col).catch(() => null),
      getLatestCache(col).catch(() => null)
    ])
    item.viewConfig = cfg
    if (cache) {
      item.createdAt = cache.created_at
      if (cache.document) {
        const sub = getByPath(cache.document, cfg?.row_path || '')
        if (Array.isArray(sub)) {
          item.rows = sub
        } else if (sub != null) {
          item.rows = [sub]
        } else {
          item.rows = []
        }
      } else {
        item.rows = []
      }
    } else {
      item.createdAt = null
      item.rows = []
      item.notFound = true
    }
  } catch (e) {
    item.notFound = true
  } finally {
    item.loading = false
  }
}

const associatedTasks = (col: string) => {
  return tasks.items.filter(t => t.kind === 'curl' && t.handler_config?.target_collection === col)
}

async function triggerCollectionTasks(col: string) {
  const list = associatedTasks(col)
  if (!list.length) return
  if (cacheTables.value[col]) {
    cacheTables.value[col].triggerLoading = true
  }
  try {
    await Promise.all(
      list.map(t => triggerTask(t.ref, {}))
    )
    ElMessage.success(`已成功手动触发 ${list.length} 个关联任务以更新缓存`)
  } catch (e: any) {
    ElMessage.error(e.message)
  } finally {
    if (cacheTables.value[col]) {
      cacheTables.value[col].triggerLoading = false
    }
  }
}

let isInitialized = false
let saveTimeout: ReturnType<typeof setTimeout> | null = null

async function saveAndCloseSettings() {
  settingsVisible.value = false
  if (saveTimeout) clearTimeout(saveTimeout)
  try {
    await upsertDashboardConfig({ config: chosenTables.value })
  } catch (e: any) {
    console.error('Failed to save dashboard config to backend:', e)
    ElMessage.error('保存展示表格配置失败: ' + e.message)
  }
}

async function loadAllChosenData() {
  await Promise.all(chosenTables.value.map(item => loadCacheTableData(item.collection)))
}

watch(chosenTables, () => {
  localStorage.setItem('dashboard_visible_tables_config', JSON.stringify(chosenTables.value))
  loadAllChosenData()
  
  if (isInitialized) {
    if (saveTimeout) clearTimeout(saveTimeout)
    saveTimeout = setTimeout(async () => {
      try {
        await upsertDashboardConfig({ config: chosenTables.value })
      } catch (e: any) {
        console.error('Failed to save dashboard config to backend:', e)
      }
    }, 1000)
  }
}, { deep: true })

useSocketListener('curl_changed', () => {
  loadAllChosenData()
})

useSocketListener('schedule_changed', () => {
  schedules.load()
})

useSocketListener('new_log', (log: TaskLog) => {
  const idx = logsList.value.findIndex(l => l.id === log.id)
  if (idx >= 0) {
    logsList.value.splice(idx, 1, log)
  } else {
    logsList.value.unshift(log)
    logsOffset.value += 1
  }
})

const allViewConfigs = ref<Record<string, CacheViewConfig>>({})

async function loadAllViewConfigs() {
  await Promise.all(
    allCollections.value.map(async (col) => {
      try {
        const cfg = await getCacheView(col)
        if (cfg) {
          allViewConfigs.value[col] = cfg
        }
      } catch {
        // ignore
      }
    })
  )
}

function isTableSelected(col: string): boolean {
  return chosenTables.value.some(t => t.collection === col)
}

function toggleTableSelection(col: string, val: any) {
  if (val) {
    if (!isTableSelected(col)) {
      chosenTables.value.push({
        collection: col,
        width: 'full',
        visibleColumns: [],
        sortBy: null,
        sortOrder: null,
        alertRules: []
      })
    }
  } else {
    chosenTables.value = chosenTables.value.filter(t => t.collection !== col)
  }
}

function getTableAlertRules(col: string): AlertRule[] {
  const t = chosenTables.value.find(t => t.collection === col)
  if (t) {
    if (!t.alertRules) {
      t.alertRules = []
    }
    return t.alertRules
  }
  return []
}

function addAlertRule(col: string) {
  const t = chosenTables.value.find(t => t.collection === col)
  if (t) {
    if (!t.alertRules) {
      t.alertRules = []
    }
    const cols = allViewConfigs.value[col]?.columns || []
    const firstColKey = cols.length > 0 ? cols[0].key : ''
    t.alertRules.push({
      column: firstColKey,
      operator: 'eq',
      value: ''
    })
  }
}

function removeAlertRule(col: string, index: number) {
  const t = chosenTables.value.find(t => t.collection === col)
  if (t && t.alertRules) {
    t.alertRules.splice(index, 1)
  }
}

function shouldAlertRow(r: any, item: DashboardTableConfig): boolean {
  if (!item.alertRules || item.alertRules.length === 0) return false
  
  return item.alertRules.some(rule => {
    if (!rule.column || !rule.operator) return false
    const val = getByPath(r, rule.column)
    
    if (rule.operator === 'is_today') {
      if (!val) return false
      try {
        const d = new Date(val as any)
        if (isNaN(d.getTime())) return false
        const today = new Date()
        return d.getFullYear() === today.getFullYear() &&
               d.getMonth() === today.getMonth() &&
               d.getDate() === today.getDate()
      } catch {
        return false
      }
    }
    
    const compVal = rule.value || ''
    
    if (rule.operator === 'eq') {
      return String(val) === compVal
    }
    if (rule.operator === 'ne') {
      return String(val) !== compVal
    }
    if (rule.operator === 'contains') {
      return val != null && String(val).toLowerCase().includes(compVal.toLowerCase())
    }
    if (rule.operator === 'gt') {
      const numVal = Number(val)
      const numComp = Number(compVal)
      return !isNaN(numVal) && !isNaN(numComp) && numVal > numComp
    }
    if (rule.operator === 'lt') {
      const numVal = Number(val)
      const numComp = Number(compVal)
      return !isNaN(numVal) && !isNaN(numComp) && numVal < numComp
    }
    
    return false
  })
}

function getTableWidth(col: string): 'third' | 'half' | 'full' {
  const t = chosenTables.value.find(t => t.collection === col)
  return t ? t.width : 'full'
}

function setTableWidth(col: string, width: any) {
  const t = chosenTables.value.find(t => t.collection === col)
  if (t) t.width = width
}

function getTableVisibleColumns(col: string): string[] {
  const t = chosenTables.value.find(t => t.collection === col)
  return t ? (t.visibleColumns || []) : []
}

function setTableVisibleColumns(col: string, columns: any) {
  const t = chosenTables.value.find(t => t.collection === col)
  if (t) t.visibleColumns = columns
}

function getTableSortBy(col: string): string | null {
  const t = chosenTables.value.find(t => t.collection === col)
  return t ? (t.sortBy || null) : null
}

function setTableSortBy(col: string, sortBy: string | null) {
  const t = chosenTables.value.find(t => t.collection === col)
  if (t) {
    t.sortBy = sortBy
    if (sortBy && !t.sortOrder) {
      t.sortOrder = 'asc'
    }
  }
}

function getTableSortOrder(col: string): 'asc' | 'desc' {
  const t = chosenTables.value.find(t => t.collection === col)
  return t ? (t.sortOrder || 'asc') : 'asc'
}

function setTableSortOrder(col: string, sortOrder: 'asc' | 'desc') {
  const t = chosenTables.value.find(t => t.collection === col)
  if (t) {
    t.sortOrder = sortOrder
  }
}

function toggleTableSort(item: DashboardTableConfig, key: string) {
  if (item.sortBy === key) {
    if (item.sortOrder === 'asc') {
      item.sortOrder = 'desc'
    } else {
      item.sortBy = null
      item.sortOrder = null
    }
  } else {
    item.sortBy = key
    item.sortOrder = 'asc'
  }
}

function getSortedRowsForTable(item: DashboardTableConfig) {
  const tableData = cacheTables.value[item.collection]
  if (!tableData || !tableData.rows) return []
  const rows = [...tableData.rows]
  if (!item.sortBy) {
    return rows
  }
  const sortBy = item.sortBy
  const sortOrder = item.sortOrder || 'asc'
  
  const colDef = tableData.viewConfig?.columns?.find(c => c.key === sortBy)
  const colType = colDef ? colDef.type : 'string'
  
  rows.sort((a, b) => {
    const valA = getByPath(a, sortBy)
    const valB = getByPath(b, sortBy)
    
    if (valA === undefined || valA === null) return 1
    if (valB === undefined || valB === null) return -1
    
    if (colType === 'number') {
      const numA = Number(valA)
      const numB = Number(valB)
      if (!isNaN(numA) && !isNaN(numB)) {
        return sortOrder === 'asc' ? numA - numB : numB - numA
      }
    }
    
    const strA = String(valA).toLowerCase()
    const strB = String(valB).toLowerCase()
    
    if (strA < strB) return sortOrder === 'asc' ? -1 : 1
    if (strA > strB) return sortOrder === 'asc' ? 1 : -1
    return 0
  })
  
  return rows
}

function getVisibleColumnsForTable(item: DashboardTableConfig) {
  const tableData = cacheTables.value[item.collection]
  if (!tableData || !tableData.viewConfig) return []
  const allCols = tableData.viewConfig.columns
  if (!item.visibleColumns || item.visibleColumns.length === 0) {
    return allCols
  }
  return allCols.filter(c => item.visibleColumns.includes(c.key))
}

onMounted(async () => {
  await tasks.load()
  
  let loaded = false
  try {
    const backendConfig = await getDashboardConfig()
    if (backendConfig && backendConfig.config && backendConfig.config.length > 0) {
      chosenTables.value = backendConfig.config
      loaded = true
    }
  } catch (e) {
    console.error('Failed to load dashboard config from backend:', e)
  }

  if (!loaded) {
    const saved = localStorage.getItem('dashboard_visible_tables_config')
    if (saved) {
      try {
        chosenTables.value = JSON.parse(saved)
      } catch {
        chosenTables.value = []
      }
    } else {
      // 默认展示第一个存在的缓存表
      if (allCollections.value.length > 0) {
        const firstCol = allCollections.value[0]
        chosenTables.value = [{
          collection: firstCol,
          width: 'full',
          visibleColumns: []
        }]
      }
    }
  }
  
  if (sidebarCollections.value.length > 0) {
    activeConfigCol.value = sidebarCollections.value[0]
  }
  
  await Promise.all([loadAllChosenData(), loadAllViewConfigs(), schedules.load(), resetLogs()])
  
  setTimeout(() => {
    isInitialized = true
  }, 100)
  
  setTimeout(attachScrollListeners, 600)
})

watch(() => stats.ready, (ready) => {
  if (ready) {
    setTimeout(attachScrollListeners, 400)
  }
})
</script>

<template>
  <div class="page-container">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px">
      <h2 class="page-title" style="margin:0">监控中心</h2>
      <el-button :icon="Setting" size="default" class="btn-configure-tables" @click="settingsVisible = true">配置展示表格</el-button>
    </div>

    <el-skeleton :loading="!stats.ready" animated :rows="6">
      <template #default>
        <!-- 选中的缓存数据表格 -->
        <div class="cache-tables-grid" style="margin-bottom:24px">
          <el-empty v-if="!chosenTables.length" description="未选择任何缓存表格，请点击右上角配置" />
          <div
            v-else
            v-for="item in chosenTables"
            :key="item.collection"
            :class="[
              'cache-table-wrapper',
              item.width === 'third' ? 'width-third' : item.width === 'half' ? 'width-half' : 'width-full'
            ]"
          >
            <div class="cache-table-header">
              <div class="cache-table-meta-left" style="display: flex; align-items: center; gap: 8px;">
                <span v-if="cacheTables[item.collection] && !cacheTables[item.collection].loading && !cacheTables[item.collection].notFound && cacheTables[item.collection].rows" class="row-count-badge">
                  {{ cacheTables[item.collection].rows.length }}
                </span>
                <h4 class="cache-table-title" style="margin: 0;">{{ item.collection }}</h4>
                <span v-if="cacheTables[item.collection] && !cacheTables[item.collection].loading && !cacheTables[item.collection].notFound" class="cache-meta-info" style="margin-left: 8px;">
                  <span v-if="cacheTables[item.collection].createdAt">
                    <b>{{ formatDateTime(cacheTables[item.collection].createdAt) }}</b>
                  </span>
                </span>
              </div>
              <div class="cache-table-actions">
                <el-tooltip
                  :content="associatedTasks(item.collection).length ? '更新缓存' : '未找到与该缓存表关联 cURL 任务'"
                  placement="top"
                >
                  <span>
                    <el-button
                      size="small"
                      type="primary"
                      link
                      class="btn-refresh-cache"
                      :icon="Refresh"
                      :disabled="!associatedTasks(item.collection).length"
                      :loading="cacheTables[item.collection]?.triggerLoading"
                      @click="triggerCollectionTasks(item.collection)"
                    />
                  </span>
                </el-tooltip>
                <el-tooltip content="查看全部数据" placement="top">
                  <router-link :to="`/cache?collection=${item.collection}`" style="margin-left: 8px;">
                    <el-button size="small" type="primary" link class="btn-arrow-right" :icon="ArrowRight" />
                  </router-link>
                </el-tooltip>
              </div>
            </div>
            
            <div v-loading="cacheTables[item.collection]?.loading">
              <el-empty v-if="cacheTables[item.collection]?.notFound" description="暂无缓存数据" size="small" style="padding:10px 0" />
              <template v-else-if="cacheTables[item.collection]?.viewConfig">
                <div class="dashboard-table-container">
                  <table class="dashboard-cols-table">
                    <thead>
                      <tr>
                        <th
                          v-for="c in getVisibleColumnsForTable(item)"
                          :key="c.key"
                          @click="toggleTableSort(item, c.key)"
                          style="cursor: pointer; user-select: none;"
                          class="sortable-header"
                          title="点击切换排序"
                        >
                          <div style="display: inline-flex; align-items: center; gap: 4px;">
                            <span>{{ c.label || c.key }}</span>
                            <span v-if="item.sortBy === c.key" class="sort-icon" style="color: var(--el-color-primary); font-weight: bold;">
                              {{ item.sortOrder === 'desc' ? '↓' : '↑' }}
                            </span>
                            <span v-else class="sort-placeholder" style="opacity: 0; transition: opacity 0.2s;">
                              ↑
                            </span>
                          </div>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="(r, ri) in getSortedRowsForTable(item).slice(0, 5)"
                        :key="ri"
                        :class="{ 'row-warning': shouldAlertRow(r, item) }"
                      >
                        <td v-for="c in getVisibleColumnsForTable(item)" :key="c.key" class="preview-cell">
                          {{ formatCellValue(getByPath(r, c.key), c.type) }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

              </template>
              <template v-else>
                <div style="padding: 20px 0; text-align: center; color: var(--el-text-color-secondary); font-size: 13px;">
                  <span>尚未配置列定义。</span>
                  <router-link :to="`/cache?collection=${item.collection}`">
                    <el-button type="primary" link size="small" style="font-size: 13px;">去配置列定义</el-button>
                  </router-link>
                </div>
              </template>
            </div>
          </div>
        </div>

        <div class="bottom-sections-row" style="margin-top: 24px; display: flex; gap: 24px; flex-wrap: wrap;">
          <!-- 任务调度 (50%) -->
          <div class="recent-schedules-section" style="flex: 1 1 calc(50% - 12px); min-width: 300px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
              <h3 style="margin:0;font-size:14px;font-weight:600">任务调度</h3>
              <el-button size="small" type="primary" link @click="openCreate">新增</el-button>
            </div>
            <el-empty v-if="!schedules.items.length" description="暂无调度" />
            <el-table
              v-else
              ref="schedulesTableRef"
              :data="visibleSchedules"
              height="350"
              size="small"
              class="recent-schedules-table"
            >
              <el-table-column label="任务" min-width="140">
                <template #default="{ row }">
                  {{ nameOf(row.task_ref) }}
                </template>
              </el-table-column>
              <el-table-column label="触发" min-width="120">
                <template #default="{ row }">
                  {{ fmtTrigger(row) }}
                </template>
              </el-table-column>
              <el-table-column label="下次运行" min-width="160">
                <template #default="{ row }">
                  <template v-if="row.next_run_time">
                    <div>{{ formatDateTime(row.next_run_time) }}</div>
                    <small style="color:var(--el-text-color-secondary)">({{ timeUntil(row.next_run_time) }})</small>
                  </template>
                  <span v-else>-</span>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="70">
                <template #default="{ row }">
                  <el-switch :model-value="row.enabled" size="small" @change="toggleSchedule(row)" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="90" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" type="primary" link @click="openEdit(row)">编辑</el-button>
                  <el-button size="small" type="danger" link @click="removeSchedule(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 最近日志 (50%) -->
          <div class="recent-logs-section" style="flex: 1 1 calc(50% - 12px); min-width: 300px;">
            <h3 style="margin:0 0 16px;font-size:14px;font-weight:600">最近日志</h3>
            <el-empty v-if="!logsList.length" description="暂无日志" />
            <el-table
              v-else
              ref="logsTableRef"
              :data="logsList"
              height="350"
              size="small"
              class="recent-logs-table"
            >
              <el-table-column prop="task_name" label="任务" min-width="120" />
              <el-table-column label="状态" width="80">
                <template #default="{ row }"><StatusTag :status="row.status" /></template>
              </el-table-column>
              <el-table-column label="耗时" width="80">
                <template #default="{ row }">{{ formatDuration(row.duration) }}</template>
              </el-table-column>
              <el-table-column label="开始时间" min-width="150">
                <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="80" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" type="primary" link @click="showDetail(row)">查看详情</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </template>
    </el-skeleton>

    <el-dialog
      v-model="terminalVisible"
      :title="`日志详情: ${selectedLog?.task_name ?? ''}`"
      width="820px"
      destroy-on-close
    >
      <LogTerminal :log="selectedLog" />
    </el-dialog>

    <!-- 新建/编辑调度对话框 -->
    <ScheduleDialog ref="scheduleDialogRef" @saved="schedules.load()" />

    <!-- 配置要展示的表格 -->
    <el-dialog v-model="settingsVisible" title="配置监控中心数据表展示" width="800px" destroy-on-close>
      <div class="settings-split-container">
        <!-- 左侧: 缓存表列表 -->
        <div class="settings-sidebar">
          <div class="sidebar-title">缓存数据表</div>
          <div class="sidebar-list">
            <div
              v-for="(col, index) in sidebarCollections"
              :key="col"
              :class="[
                'sidebar-item',
                activeConfigCol === col ? 'is-active' : '',
                isTableSelected(col) ? 'is-draggable' : '',
                dragOverIndex === index && isTableSelected(col) ? 'drag-over' : ''
              ]"
              :draggable="isTableSelected(col)"
              @dragstart="onDragStart(index)"
              @dragover="onDragOver"
              @dragenter="onDragEnter(index)"
              @dragleave="onDragLeave"
              @drop="onDrop(index)"
              @click="activeConfigCol = col"
            >
              <!-- 拖动手柄 (仅对选中的表格展示) -->
              <span v-if="isTableSelected(col)" class="drag-handle" style="margin-right: 4px; display: flex; align-items: center; color: var(--muted); opacity: 0.6;">
                <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M5 3a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0zm5 0a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0zm5 0a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0zM5 8a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0zm5 0a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0zm5 0a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0zm-10 5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0zm5 0a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0zm5 0a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0z"/>
                </svg>
              </span>
              
              <el-checkbox
                :model-value="isTableSelected(col)"
                @change="(val: any) => toggleTableSelection(col, val)"
                @click.stop
              />
              <span class="sidebar-item-label" style="text-overflow: ellipsis; overflow: hidden; white-space: nowrap; max-width: 120px;" :title="col">{{ col }}</span>
              <el-tag
                v-if="!allCollections.includes(col)"
                type="danger"
                size="small"
                effect="light"
                style="margin-left: 8px; height: 18px; line-height: 16px; padding: 0 4px;"
              >
                已失效
              </el-tag>
            </div>
          </div>
        </div>

        <!-- 右侧: 当前选中表的具体配置 -->
        <div class="settings-detail">
          <template v-if="activeConfigCol">
            <div class="detail-title">
              配置: <span class="highlight">{{ activeConfigCol }}</span>
            </div>
            
            <div v-if="isTableSelected(activeConfigCol)" class="detail-body">
              <!-- 宽度配置 -->
              <div class="detail-section">
                <div class="detail-section-title">卡片展示宽度</div>
                <el-radio-group
                  :model-value="getTableWidth(activeConfigCol)"
                  @change="(val: any) => setTableWidth(activeConfigCol!, val)"
                  size="default"
                >
                  <el-radio-button value="third">1/3 宽度 (33%)</el-radio-button>
                  <el-radio-button value="half">1/2 宽度 (50%)</el-radio-button>
                  <el-radio-button value="full">整行展示 (100%)</el-radio-button>
                </el-radio-group>
              </div>

              <!-- 显示列配置 -->
              <div class="detail-section">
                <div class="detail-section-title">要展示的列</div>
                <div v-if="allViewConfigs[activeConfigCol]?.columns?.length" class="columns-selector-grid">
                  <el-checkbox-group
                    :model-value="getTableVisibleColumns(activeConfigCol)"
                    @change="(val: any) => setTableVisibleColumns(activeConfigCol!, val)"
                    class="dialog-checkbox-group"
                  >
                    <el-checkbox
                      v-for="c in allViewConfigs[activeConfigCol].columns"
                      :key="c.key"
                      :value="c.key"
                      class="col-checkbox"
                    >
                      {{ c.label || c.key }}
                    </el-checkbox>
                  </el-checkbox-group>
                </div>
                <div v-else class="detail-hint">
                  此数据表尚未配置列定义，将默认显示全部推断出的列。
                </div>
              </div>

              <!-- 排序配置 -->
              <div class="detail-section">
                <div class="detail-section-title">默认排序列</div>
                <div style="display: flex; flex-wrap: wrap; gap: 12px; align-items: center;">
                  <el-select
                    :model-value="getTableSortBy(activeConfigCol)"
                    @change="(val: any) => setTableSortBy(activeConfigCol!, val)"
                    placeholder="请选择排序列"
                    clearable
                    size="default"
                    style="width: 200px;"
                  >
                    <el-option
                      v-for="c in (allViewConfigs[activeConfigCol]?.columns || [])"
                      :key="c.key"
                      :label="c.label || c.key"
                      :value="c.key"
                    />
                  </el-select>

                  <el-radio-group
                    v-if="getTableSortBy(activeConfigCol)"
                    :model-value="getTableSortOrder(activeConfigCol)"
                    @change="(val: any) => setTableSortOrder(activeConfigCol!, val)"
                    size="default"
                  >
                    <el-radio-button value="asc">升序</el-radio-button>
                    <el-radio-button value="desc">降序</el-radio-button>
                  </el-radio-group>
                </div>
              </div>

              <!-- 警示规则配置 -->
              <div class="detail-section">
                <div class="detail-section-title">数据行警示规则 (满足条件时，该行以警示色显示)</div>
                <div v-if="getTableAlertRules(activeConfigCol).length" class="alert-rules-list" style="display: flex; flex-direction: column; gap: 8px;">
                  <div
                    v-for="(rule, rIdx) in getTableAlertRules(activeConfigCol)"
                    :key="rIdx"
                    style="display: flex; gap: 8px; align-items: center;"
                  >
                    <el-select
                      v-model="rule.column"
                      placeholder="选择列"
                      size="default"
                      style="width: 160px;"
                    >
                      <el-option
                        v-for="c in (allViewConfigs[activeConfigCol]?.columns || [])"
                        :key="c.key"
                        :label="c.label || c.key"
                        :value="c.key"
                      />
                    </el-select>

                    <el-select
                      v-model="rule.operator"
                      placeholder="条件"
                      size="default"
                      style="width: 120px;"
                    >
                      <el-option value="eq" label="等于" />
                      <el-option value="ne" label="不等于" />
                      <el-option value="contains" label="包含" />
                      <el-option value="gt" label="大于" />
                      <el-option value="lt" label="小于" />
                      <el-option value="is_today" label="日期是今天" />
                    </el-select>

                    <el-input
                      v-if="rule.operator !== 'is_today'"
                      v-model="rule.value"
                      placeholder="值"
                      size="default"
                      style="width: 140px;"
                    />

                    <el-button
                      type="danger"
                      link
                      size="default"
                      :icon="Delete"
                      @click="removeAlertRule(activeConfigCol!, rIdx)"
                    />
                  </div>
                </div>
                <div style="margin-top: 4px;">
                  <el-button type="primary" plain size="small" :icon="Plus" @click="addAlertRule(activeConfigCol!)">
                    添加警示规则
                  </el-button>
                </div>
              </div>
            </div>
            
            <div v-else class="detail-empty-state">
              <el-empty description="该数据表未启用，请在左侧勾选启用后再进行配置" :image-size="80" />
            </div>
          </template>
          
          <div v-else class="detail-empty-state">
            <el-empty description="请从左侧选择一个数据表进行配置" :image-size="80" />
          </div>
        </div>
      </div>

      <template #footer>
        <el-button type="primary" @click="saveAndCloseSettings">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.cache-table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
.cache-table-meta-left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.cache-table-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}
.cache-meta-info {
  display: flex;
  gap: 14px;
  font-size: 11px;
  color: var(--muted);
}
.row-count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  height: 20px;
  min-width: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--accents-1);
  border: 1px solid var(--border);
  color: var(--muted);
  font-family: 'Geist Mono', 'JetBrains Mono', monospace;
  box-sizing: border-box;
}
.dashboard-table-container {
  overflow-x: auto;
}
.dashboard-cols-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.dashboard-cols-table th,
.dashboard-cols-table td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}
.dashboard-cols-table th {
  background: var(--accents-1);
  color: var(--muted);
  font-weight: 500;
  text-align: left;
}
.dashboard-cols-table tr:last-child td {
  border-bottom: none;
}
.preview-cell {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'Geist Mono', 'JetBrains Mono', 'SF Mono', Menlo, monospace;
}
.more-hint {
  font-size: 11px;
  color: var(--muted);
  margin-top: 8px;
  text-align: right;
}
.vertical-checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
  border: 1px solid var(--border);
  padding: 12px;
  border-radius: var(--radius);
}
.cache-tables-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
}
.cache-table-wrapper {
  min-width: 0;
  box-sizing: border-box;
  border: 1px dashed var(--border);
  border-radius: var(--radius);
  padding: 16px;
  background: var(--surface);
  transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
}
.cache-table-wrapper:hover {
  border-style: solid;
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.15);
  transform: translateY(-2px);
}
.width-third {
  flex: 0 0 calc(33.333% - 13.33px);
}
.width-half {
  flex: 0 0 calc(50% - 10px);
}
.width-full {
  flex: 0 0 100%;
}
@media (max-width: 768px) {
  .width-third,
  .width-half {
    flex: 0 0 100%;
  }
}
.settings-split-container {
  display: flex;
  height: 420px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--card-bg);
}
.settings-sidebar {
  width: 240px;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  background: var(--accents-1);
}
.sidebar-title {
  padding: 10px 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  border-bottom: 1px solid var(--border);
}
.sidebar-list {
  flex: 1;
  overflow-y: auto;
}
.sidebar-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
  transition: all 0.2s cubic-bezier(0.25, 0.8, 0.25, 1);
  border-left: 3px solid transparent;
}
.sidebar-item:hover {
  background: rgba(255, 255, 255, 0.05);
  padding-left: 18px;
}
.sidebar-item.is-active {
  background: rgba(255, 255, 255, 0.08);
  border-left: 3px solid var(--el-color-primary);
}
.sidebar-item :deep(.el-checkbox) {
  margin-right: 0 !important;
}
.sidebar-item :deep(.el-checkbox__label) {
  display: none !important;
}
.sidebar-item-label {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sidebar-item.is-draggable {
  user-select: none;
}
.sidebar-item.is-draggable .drag-handle {
  cursor: grab;
}
.sidebar-item.is-draggable:active {
  cursor: grabbing;
}
.sidebar-item.drag-over {
  background: rgba(64, 158, 255, 0.15) !important;
  border-top: 1px dashed var(--el-color-primary);
  border-bottom: 1px dashed var(--el-color-primary);
}
.settings-detail {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.detail-title {
  font-size: 15px;
  font-weight: 600;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
.detail-title .highlight {
  color: var(--el-color-primary);
}
.detail-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.detail-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.detail-section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
}
.detail-hint {
  font-size: 12px;
  color: var(--muted);
  font-style: italic;
}
.detail-empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.columns-selector-grid {
  max-height: 200px;
  overflow-y: auto;
}
.dialog-checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
}
.col-checkbox {
  margin-right: 0 !important;
}
.recent-schedules-table,
.recent-logs-table {
  border: none !important;
}
.recent-schedules-table :deep(.el-table__inner-wrapper::before),
.recent-logs-table :deep(.el-table__inner-wrapper::before) {
  display: none !important;
}
.recent-schedules-table :deep(.el-table__cell),
.recent-logs-table :deep(.el-table__cell) {
  padding: 6px 0 !important;
}
.page-container {
  max-width: 100% !important;
}
.sortable-header {
  transition: background-color 0.2s;
}
.sortable-header:hover {
  background: var(--accents-2) !important;
}
.sortable-header:hover .sort-placeholder {
  opacity: 0.6 !important;
}
.row-warning {
  background-color: rgba(245, 108, 108, 0.15) !important;
  color: var(--el-color-danger) !important;
}
.row-warning:hover {
  background-color: rgba(245, 108, 108, 0.25) !important;
}
.row-warning td {
  border-bottom: 1px solid rgba(245, 108, 108, 0.3) !important;
}
.btn-configure-tables :deep(.el-icon) {
  transition: transform 0.4s ease;
}
.btn-configure-tables:hover :deep(.el-icon) {
  transform: rotate(180deg);
}
.btn-refresh-cache {
  transition: transform 0.3s ease;
}
.btn-refresh-cache:hover:not(.is-disabled) {
  transform: rotate(180deg) scale(1.1);
}
.btn-arrow-right {
  transition: transform 0.2s ease;
}
.btn-arrow-right:hover {
  transform: translateX(3px) scale(1.1);
}
.dashboard-cols-table tr {
  transition: background-color 0.2s ease;
}
:deep(.el-table__row) {
  transition: background-color 0.2s ease;
}
</style>
