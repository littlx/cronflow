<script setup lang="ts">
import { useStatsStore } from '@/stores/stats'
const stats = useStatsStore()
</script>

<template>
  <h2 class="page-title">监控中心</h2>
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
    <h3 style="margin-bottom:12px">最近日志</h3>
    <el-empty v-if="!stats.logs.length" description="暂无日志" />
    <el-table v-else :data="stats.logs" size="small">
      <el-table-column prop="task_name" label="任务" min-width="140" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status==='success'?'success':row.status==='failed'?'danger':'warning'" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="trigger_type" label="触发" width="100" />
      <el-table-column prop="duration" label="耗时(s)" width="100" />
      <el-table-column prop="started_at" label="开始时间" min-width="180" />
    </el-table>
  </div>
</template>
