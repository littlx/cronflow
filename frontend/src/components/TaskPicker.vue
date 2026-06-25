<!--
  TaskPicker — 任务选择器, 把 python (tag=primary) 与 curl (tag=success)
  分组展示, 支持搜索过滤。SchedulesView 新建调度时使用。

  v-model 绑定 task_ref 字符串。
-->
<script setup lang="ts">
import { computed } from 'vue'
import { useTasksStore } from '@/stores/tasks'

const props = defineProps<{ modelValue: string; disabled?: boolean }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>()

const tasks = useTasksStore()

const pythonTasks = computed(() => tasks.python)
const curlTasks = computed(() => tasks.curl)

const local = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
</script>

<template>
  <el-select v-model="local" filterable placeholder="选择任意 python / curl 任务" style="width:100%" :disabled="disabled">
    <el-option-group label="Python (代码注册)">
      <el-option v-for="t in pythonTasks" :key="t.ref" :label="t.name" :value="t.ref">
        <span style="float:left">{{ t.name }}</span>
        <span style="float:right;color:var(--el-text-color-secondary);font-size:12px">{{ t.ref }}</span>
      </el-option>
    </el-option-group>
    <el-option-group label="cURL (表单配置)">
      <el-option v-for="t in curlTasks" :key="t.ref" :label="t.name" :value="t.ref">
        <span style="float:left">{{ t.name }}</span>
        <span style="float:right;color:var(--el-text-color-secondary);font-size:12px">{{ t.handler_config?.url }}</span>
      </el-option>
    </el-option-group>
  </el-select>
</template>
