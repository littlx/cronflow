<!--
  LogsView — 执行日志
  - 分页 (useTable composable, 与后端 /api/logs 的 limit/offset 对接)
  - 筛选: task_ref / status
  - 详情弹窗 (复用 LogTerminal)
  - 实时推送: new_log 时自动刷新当前页 (若在首页)
-->
<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { listLogs } from '@/api/logs'
import { useTable } from '@/composables/useTable'
import { useSocketListener } from '@/composables/useSocket'
import StatusTag from '@/components/StatusTag.vue'
import LogTerminal from '@/components/LogTerminal.vue'
import { formatDateTime, formatDuration } from '@/utils/format'
import type { TaskLog } from '@/api/types'

const filterRef = ref('')
const filterStatus = ref('')

const table = useTable<TaskLog>({
  fetcher: (params) => listLogs({
    ...params,
    task_ref: filterRef.value || undefined,
    status: filterStatus.value || undefined,
  }),
  pageSize: 50,
})

function onSearch() { table.refresh() }

// 详情
const terminalVisible = ref(false)
const selectedLog = ref<TaskLog | null>(null)
function showDetail(row: TaskLog) {
  selectedLog.value = row
  terminalVisible.value = true
}

function triggerLabel(t: string) {
  return { interval: '间隔', cron: 'Cron', manual: '手动' }[t] || t
}

// 收到新日志事件 + 当前在第一页 → 刷新, 让用户即时看到
useSocketListener('new_log', () => {
  if (table.page.value === 1) {
    table.load()
  }
})

onMounted(() => table.load())
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">执行日志</h2>
    <div class="panel">
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
        <el-input
          v-model="filterRef"
          placeholder="按 task_ref 过滤"
          clearable
          style="width:280px"
          @clear="onSearch"
          @keyup.enter="onSearch"
        />
        <el-select v-model="filterStatus" placeholder="状态" clearable style="width:140px" @change="onSearch" @clear="onSearch">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
          <el-option label="运行中" value="running" />
        </el-select>
        <el-button @click="onSearch">查询</el-button>
      </div>

      <el-empty v-if="!table.items.value.length && !table.loading.value" description="暂无日志" />
      <el-table v-else :data="table.items.value" v-loading="table.loading.value" size="small">
        <el-table-column prop="task_name" label="任务" min-width="160" />
        <el-table-column label="ref" min-width="200" show-overflow-tooltip>
          <template #default="{ row }"><code>{{ row.task_ref }}</code></template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }"><StatusTag :status="row.status" /></template>
        </el-table-column>
        <el-table-column label="触发" width="100">
          <template #default="{ row }">{{ triggerLabel(row.trigger_type) }}</template>
        </el-table-column>
        <el-table-column label="第几次" width="80">
          <template #default="{ row }">#{{ row.attempt }}</template>
        </el-table-column>
        <el-table-column label="耗时" width="100">
          <template #default="{ row }">{{ formatDuration(row.duration) }}</template>
        </el-table-column>
        <el-table-column label="开始" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column prop="error" label="错误" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="showDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="table.total.value > 0" style="display:flex;justify-content:flex-end;margin-top:12px">
        <el-pagination
          :current-page="table.page.value"
          :page-size="table.pageSize.value"
          :total="table.total.value"
          :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="table.onPageChange"
          @size-change="table.onPageSizeChange"
        />
      </div>
    </div>

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
