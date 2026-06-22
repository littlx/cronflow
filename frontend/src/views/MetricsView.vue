<!--
  MetricsView — Prometheus 指标可视化。

  直接 GET /metrics (text format), 用简单的正则提取 cronflow_* 系列指标,
  按指标分组展示 (counter / gauge / histogram)。
  3 人内网够用; 未来如需图表可接 grafana, 这里只做"能看"。
-->
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import MetricCard from '@/components/MetricCard.vue'
import { DataLine, Cpu, Calendar, CircleCheck } from '@element-plus/icons-vue'

interface MetricLine {
  name: string
  labels: Record<string, string>
  value: number
}

const rawText = ref('')
const loading = ref(false)
const refreshing = ref(false)
const lastFetched = ref<Date | null>(null)
let timer: ReturnType<typeof setInterval> | null = null

async function fetchMetrics() {
  refreshing.value = true
  try {
    // 直接打 /metrics (与 /api 同级, 不走 axios baseURL)
    const r = await axios.get('/metrics', { timeout: 10000 })
    rawText.value = r.data
    lastFetched.value = new Date()
  } catch (e: any) {
    ElMessage.error('拉取 /metrics 失败: ' + e.message)
  } finally {
    refreshing.value = false
    loading.value = false
  }
}

// 解析 prometheus text 格式中 cronflow_* 行
const LINE_RE = /^([a-zA-Z_][a-zA-Z0-9_]*)(\{([^}]*)\})?\s+([\d.eE+\-]+)/

function parseLabels(s: string): Record<string, string> {
  const out: Record<string, string> = {}
  // labels 形如  task_ref="x",status="success"
  const re = /([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"/g
  let m: RegExpExecArray | null
  while ((m = re.exec(s)) !== null) {
    out[m[1]] = m[2].replace(/\\"/g, '"')
  }
  return out
}

const metrics = computed<MetricLine[]>(() => {
  const lines: MetricLine[] = []
  for (const raw of rawText.value.split('\n')) {
    const line = raw.trim()
    if (!line || line.startsWith('#')) continue
    if (!line.startsWith('cronflow_')) continue
    const m = line.match(LINE_RE)
    if (!m) continue
    const name = m[1]
    const labelsStr = m[3] || ''
    const value = Number(m[4])
    lines.push({ name, labels: parseLabels(labelsStr), value: isNaN(value) ? 0 : value })
  }
  return lines
})

const groupedByName = computed(() => {
  const out: Record<string, MetricLine[]> = {}
  for (const m of metrics.value) {
    if (!out[m.name]) out[m.name] = []
    out[m.name].push(m)
  }
  return out
})

// 顶部指标卡片: 几个关键聚合值
const summary = computed(() => {
  const taskTotalLines = metrics.value.filter((m) => m.name === 'cronflow_task_total')
  const total = taskTotalLines.reduce((acc, l) => acc + l.value, 0)
  const success = taskTotalLines.filter((l) => l.labels.status === 'success').reduce((a, l) => a + l.value, 0)
  const failed = taskTotalLines.filter((l) => l.labels.status === 'failed').reduce((a, l) => a + l.value, 0)
  const activeSch = metrics.value.find((m) => m.name === 'cronflow_active_schedules')?.value ?? 0
  const registered = metrics.value.find((m) => m.name === 'cronflow_registered_tasks')?.value ?? 0
  return {
    total: Math.round(total),
    success: Math.round(success),
    failed: Math.round(failed),
    active_schedules: Math.round(activeSch),
    registered_tasks: Math.round(registered),
  }
})

onMounted(async () => {
  loading.value = true
  await fetchMetrics()
  timer = setInterval(fetchMetrics, 10000)  // 每 10 秒刷新
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">指标</h2>

    <el-skeleton :loading="loading" animated :rows="6">
      <template #default>
        <div class="grid grid-4" style="margin-bottom:20px">
          <MetricCard label="已注册任务" :value="summary.registered_tasks" :icon="Cpu" variant="info" />
          <MetricCard label="启用调度数" :value="summary.active_schedules" :icon="Calendar" variant="brand" />
          <MetricCard label="累计执行(成功)" :value="summary.success" :icon="CircleCheck" variant="success" />
          <MetricCard label="累计执行(失败)" :value="summary.failed" :icon="DataLine" variant="danger" />
        </div>

        <div class="panel">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <h3 style="margin:0;font-size:14px;font-weight:600">
              cronflow_* 指标明细
              <span v-if="lastFetched" style="font-size:11px;color:var(--el-text-color-secondary);font-weight:normal">
                · 最近刷新 {{ lastFetched.toLocaleTimeString() }}
              </span>
            </h3>
            <el-button size="small" :loading="refreshing" @click="fetchMetrics">手动刷新</el-button>
          </div>
          <el-empty v-if="!metrics.length" description="暂无 cronflow_* 指标 (触发一次任务后将出现)" />
          <div v-else>
            <div v-for="(rows, name) in groupedByName" :key="name" class="metric-group">
              <div class="metric-name"><code>{{ name }}</code></div>
              <el-table :data="rows" size="small" :show-header="true">
                <el-table-column label="labels" min-width="320">
                  <template #default="{ row }">
                    <code v-if="Object.keys(row.labels).length">
                      {{ Object.entries(row.labels).map(([k,v]) => `${k}=${v}`).join(', ') }}
                    </code>
                    <span v-else style="color:var(--el-text-color-secondary)">(no labels)</span>
                  </template>
                </el-table-column>
                <el-table-column label="value" width="160" align="right">
                  <template #default="{ row }">
                    <b>{{ row.value }}</b>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>
        </div>
      </template>
    </el-skeleton>
  </div>
</template>

<style scoped>
.metric-group {
  margin-bottom: 18px;
}
.metric-name {
  font-size: 12.5px;
  font-weight: 500;
  margin-bottom: 6px;
  color: var(--muted);
}
code {
  font-family: 'Geist Mono', 'JetBrains Mono', 'SF Mono', Menlo, monospace;
  font-size: 12px;
  background: var(--accents-1);
  border: 1px solid var(--border);
  padding: 1px 6px;
  border-radius: 4px;
  color: var(--fg);
}
</style>