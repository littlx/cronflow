<script setup lang="ts">
import { ref } from 'vue'
import { useStatsStore } from '@/stores/stats'
import { ElMessage } from 'element-plus'

const stats = useStatsStore()

const terminalVisible = ref(false)
const selectedLog = ref<any>(null)

function showTerminal(row: any) {
  selectedLog.value = row
  terminalVisible.value = true
}

function formatLogContent(val: any) {
  if (!val) return 'No output returned.'
  if (typeof val === 'object') {
    return JSON.stringify(val, null, 2)
  }
  try {
    const parsed = JSON.parse(val)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return String(val)
  }
}

async function copyLogContent() {
  if (!selectedLog.value) return
  const text = selectedLog.value.status === 'success'
    ? `[INFO] Task executed successfully. Return value:\n${formatLogContent(selectedLog.value.result)}`
    : `[ERROR] Task execution failed:\n${selectedLog.value.error}${selectedLog.value.result ? `\n\n[INFO] Partial result:\n${formatLogContent(selectedLog.value.result)}` : ''}`
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('日志已复制到剪贴板')
  } catch (err) {
    ElMessage.error('复制失败')
  }
}
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">监控中心</h2>
    
    <el-skeleton :loading="!stats.ready" animated>
      <template #template>
        <div class="grid grid-4" style="margin-bottom: 20px;">
          <el-skeleton-item variant="rect" style="height: 100px; border-radius: var(--radius-lg);" v-for="i in 4" :key="i" />
        </div>
        <div class="panel">
          <el-skeleton-item variant="h3" style="width: 20%; margin-bottom: 16px; height: 20px;" />
          <el-skeleton-item variant="text" style="margin-bottom: 12px; height: 16px;" v-for="i in 5" :key="i" />
        </div>
      </template>
      <template #default>
        <div class="grid grid-4">
          <div class="metric-card">
            <div class="label">活跃调度 / 总调度</div>
            <div class="value">{{ stats.data?.active_schedules ?? '-' }} / {{ stats.data?.total_schedules ?? '-' }}</div>
          </div>
          <div class="metric-card">
            <div class="label">执行成功率</div>
            <div class="value">{{ stats.data?.success_rate ?? '-' }}%</div>
          </div>
          <div class="metric-card">
            <div class="label">累计运行 / 运行中</div>
            <div class="value">{{ stats.data?.total_runs ?? '-' }} / {{ stats.data?.running_runs ?? '-' }}</div>
          </div>
          <div class="metric-card">
            <div class="label">CPU / 内存</div>
            <div class="value">{{ stats.data?.system?.cpu_usage ?? '-' }}% / {{ stats.data?.system?.memory_usage ?? '-' }}%</div>
          </div>
        </div>

        <div class="panel">
          <h3 style="margin-bottom:16px">最近日志</h3>
          <el-empty v-if="!stats.logs.length" description="暂无日志" />
          <el-table v-else :data="stats.logs" size="small">
            <el-table-column prop="task_name" label="任务" min-width="140" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <span :class="['status-dot', 
                  row.status === 'success' ? 'status-dot--success' : 
                  row.status === 'failed' ? 'status-dot--danger' : 
                  row.status === 'running' ? 'status-dot--info status-dot--running' : 'status-dot--warning'
                ]">
                  {{ row.status }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="trigger_type" label="触发" width="100" />
            <el-table-column prop="duration" label="耗时(s)" width="100" />
            <el-table-column prop="started_at" label="开始时间" min-width="180" />
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" link @click="showTerminal(row)">查看详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>
    </el-skeleton>

    <!-- Terminal Simulator Dialog -->
    <el-dialog v-model="terminalVisible" :title="`运行日志详情: ${selectedLog?.task_name}`" width="800px">
      <div v-if="selectedLog" class="terminal-container">
        <div class="terminal-header">
          <div class="terminal-dots">
            <span class="dot red"></span>
            <span class="dot yellow"></span>
            <span class="dot green"></span>
          </div>
          <div class="terminal-title">bash - log_output.log</div>
          <el-button size="small" type="info" class="terminal-copy" @click="copyLogContent">复制日志</el-button>
        </div>
        <div class="terminal-body">
          <div class="meta-section">
            <div><span class="lbl">ID:</span> #{{ selectedLog.id }}</div>
            <div><span class="lbl">状态:</span> 
              <span :class="['status-dot', selectedLog.status === 'success' ? 'status-dot--success' : 'status-dot--danger']">{{ selectedLog.status }}</span>
            </div>
            <div><span class="lbl">触发:</span> {{ selectedLog.trigger_type }}</div>
            <div><span class="lbl">耗时:</span> {{ selectedLog.duration ?? '-' }}s</div>
            <div><span class="lbl">时间:</span> {{ selectedLog.started_at }}</div>
          </div>
          <hr class="terminal-divider" />
          <div class="console-output">
            <template v-if="selectedLog.status === 'success'">
              <div class="console-line line-info">[INFO] Task executed successfully. Return value:</div>
              <pre class="console-code">{{ formatLogContent(selectedLog.result) }}</pre>
            </template>
            <template v-else>
              <div class="console-line line-error">[ERROR] Task execution failed:</div>
              <pre class="console-code error-text">{{ selectedLog.error }}</pre>
              <div v-if="selectedLog.result" class="console-line line-info">[INFO] Partial result:</div>
              <pre v-if="selectedLog.result" class="console-code">{{ formatLogContent(selectedLog.result) }}</pre>
            </template>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

