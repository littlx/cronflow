<!--
  DashboardView — 监控中心
  - 4 个指标卡片 (复用 MetricCard)
  - 最近日志表格 (复用 LogTerminal 详情)

  数据全部来自 useStatsStore (全局 socket + 初始 fetch), 本组件无独立请求。
-->
<script setup lang="ts">
import { ref } from 'vue'
import { Calendar, CircleCheck, Odometer, Cpu } from '@element-plus/icons-vue'
import { useStatsStore } from '@/stores/stats'
import MetricCard from '@/components/MetricCard.vue'
import StatusTag from '@/components/StatusTag.vue'
import LogTerminal from '@/components/LogTerminal.vue'
import type { TaskLog } from '@/api/types'
import { formatDateTime, formatDuration } from '@/utils/format'

const stats = useStatsStore()

const terminalVisible = ref(false)
const selectedLog = ref<TaskLog | null>(null)
function showDetail(row: TaskLog) {
  selectedLog.value = row
  terminalVisible.value = true
}

function triggerLabel(t: string) {
  return { interval: '间隔', cron: 'Cron', manual: '手动' }[t] || t
}
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">监控中心</h2>

    <el-skeleton :loading="!stats.ready" animated :rows="6">
      <template #default>
        <div class="grid grid-4" style="margin-bottom:20px">
          <MetricCard
            label="活跃调度 / 总调度"
            :value="`${stats.data?.active_schedules ?? '-'} / ${stats.data?.total_schedules ?? '-'}`"
            :icon="Calendar"
            variant="brand"
          />
          <MetricCard
            label="执行成功率"
            :value="`${stats.data?.success_rate ?? 0}%`"
            :icon="CircleCheck"
            variant="success"
          />
          <MetricCard
            label="累计运行 / 运行中"
            :value="`${stats.data?.total_runs ?? '-'} / ${stats.data?.running_runs ?? '-'}`"
            :icon="Odometer"
            variant="warning"
          />
          <MetricCard
            label="CPU / 内存"
            :value="`${stats.data?.system?.cpu_usage ?? '-'}% / ${stats.data?.system?.memory_usage ?? '-'}%`"
            :icon="Cpu"
            variant="info"
          />
        </div>

        <div class="panel">
          <h3 style="margin:0 0 16px;font-size:14px;font-weight:600">最近日志</h3>
          <el-empty v-if="!stats.logs.length" description="暂无日志" />
          <el-table v-else :data="stats.logs" size="small">
            <el-table-column prop="task_name" label="任务" min-width="160" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }"><StatusTag :status="row.status" /></template>
            </el-table-column>
            <el-table-column label="触发" width="100">
              <template #default="{ row }">{{ triggerLabel(row.trigger_type) }}</template>
            </el-table-column>
            <el-table-column label="耗时" width="100">
              <template #default="{ row }">{{ formatDuration(row.duration) }}</template>
            </el-table-column>
            <el-table-column label="开始时间" min-width="180">
              <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" link @click="showDetail(row)">查看详情</el-button>
              </template>
            </el-table-column>
          </el-table>
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
  </div>
</template>
