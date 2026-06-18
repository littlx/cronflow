<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '@/api/client'
import { ElMessage } from 'element-plus'

interface TaskParam { name: string; type: string; default: any; required: boolean }
interface TaskDef { id: string; name: string; description: string; module: string; parameters: TaskParam[] }

const tasks = ref<TaskDef[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const { data } = await client.get<TaskDef[]>('/tasks')
    tasks.value = data
  } finally { loading.value = false }
}

async function trigger(task: TaskDef) {
  try {
    await client.post('/tasks/trigger', { task_id: task.id, task_args: {} })
    ElMessage.success(`已触发: ${task.name}`)
  } catch (e: any) { ElMessage.error(e.message) }
}

onMounted(load)
</script>

<template>
  <h2 class="page-title">任务注册</h2>
  <div class="panel">
    <el-empty v-if="!tasks.length" description="暂无注册任务" />
    <el-table v-else :data="tasks" v-loading="loading" size="default">
      <el-table-column prop="name" label="任务名" min-width="160" />
      <el-table-column prop="id" label="ID" min-width="200" />
      <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
      <el-table-column label="参数" width="120">
        <template #default="{ row }">{{ row.parameters?.length ?? 0 }} 个</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="trigger(row)">立即执行</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
