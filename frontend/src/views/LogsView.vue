<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '@/api/client'

const logs = ref<any[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try { const { data } = await client.get('/logs'); logs.value = data }
  finally { loading.value = false }
}

onMounted(load)
</script>

<template>
  <h2 class="page-title">执行日志</h2>
  <div class="panel">
    <el-empty v-if="!logs.length" description="暂无日志" />
    <el-table v-else :data="logs" v-loading="loading" size="small">
      <el-table-column prop="task_name" label="任务" min-width="140" />
      <el-table-column prop="status" label="状态" width="90" />
      <el-table-column prop="trigger_type" label="触发" width="90" />
      <el-table-column prop="duration" label="耗时(s)" width="100" />
      <el-table-column prop="started_at" label="开始" min-width="180" />
      <el-table-column prop="error" label="错误" min-width="200" show-overflow-tooltip />
    </el-table>
  </div>
</template>
