<!--
  CacheView — 缓存数据查询 (单条 upsert)。

  缓存语义改为 upsert: 每个 target_collection 最多一条记录,
  每次 curl 任务执行覆盖旧的。这里直接用 /latest 接口取唯一一条。
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getLatestCache } from '@/api/cache'
import { useTasksStore } from '@/stores/tasks'
import { useSocketListener } from '@/composables/useSocket'
import { formatDateTime } from '@/utils/format'
import type { CacheItem } from '@/api/types'

const tasks = useTasksStore()

const collection = ref('')
const current = ref<CacheItem | null>(null)
const loading = ref(false)
const notFound = ref(false)

// curl 任务的 target_collection 备选列表
const collectionsFromTasks = () => {
  const set = new Set<string>()
  for (const t of tasks.curl) {
    const c = t.handler_config?.target_collection
    if (c) set.add(c)
  }
  return Array.from(set)
}
const suggestions = ref<string[]>([])

async function load() {
  if (!collection.value.trim()) return
  loading.value = true
  notFound.value = false
  current.value = null
  try {
    current.value = await getLatestCache(collection.value.trim())
  } catch (e: any) {
    if ((e?.message || '').includes('没有缓存数据') || (e?.message || '').includes('404')) {
      notFound.value = true
    } else {
      ElMessage.error(e.message)
    }
  } finally {
    loading.value = false
  }
}

// curl 任务执行成功后会广播 curl_changed, 这里如果当前选中的 collection
// 在被刷新, 自动重新拉取一次
useSocketListener('curl_changed', () => {
  if (collection.value) load()
})

onMounted(async () => {
  if (!tasks.items.length) await tasks.load()
  suggestions.value = collectionsFromTasks()
  // 自动选第一个并加载
  if (suggestions.value.length) {
    collection.value = suggestions.value[0]
    await load()
  }
})
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">缓存数据</h2>
    <div class="panel">
      <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
        <el-select
          v-model="collection"
          filterable allow-create default-first-option
          placeholder="选择或输入 target_collection"
          style="width:360px"
          @change="load"
        >
          <el-option v-for="c in suggestions" :key="c" :label="c" :value="c" />
        </el-select>
        <el-button type="primary" @click="load">查询</el-button>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>

      <el-empty v-if="!collection" description="选择或输入一个 target_collection 查看最新缓存" />
      <el-empty v-else-if="notFound" :description="`暂无缓存数据 (collection: ${collection})`" />
      <template v-else-if="current">
        <div class="meta">
          <span>id: <code>{{ current.id }}</code></span>
          <span>collection: <code>{{ current.target_collection }}</code></span>
          <span>更新时间: {{ formatDateTime(current.created_at) }}</span>
        </div>
        <pre class="cache-doc">{{ JSON.stringify(current.document, null, 2) }}</pre>
      </template>
      <el-skeleton v-else-if="loading" :rows="6" animated />
    </div>
  </div>
</template>

<style scoped>
.meta {
  display: flex;
  gap: 18px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.meta code {
  color: var(--el-text-color-primary);
  background: var(--el-fill-color-light);
  padding: 1px 6px;
  border-radius: 3px;
}
.cache-doc {
  background: #0d1117;
  color: #c9d1d9;
  padding: 14px 16px;
  border-radius: 6px;
  font-size: 12.5px;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  overflow: auto;
  max-height: 640px;
}
</style>