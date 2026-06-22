<!--
  CacheView — 缓存数据查询 (分页)。
  通过下拉选择 collection 或手动输入, 调 /api/cache/{collection}。
-->
<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { listCache } from '@/api/cache'
import { useTable } from '@/composables/useTable'
import { formatDateTime } from '@/utils/format'
import type { CacheItem } from '@/api/types'

const collection = ref('')
const inputFocused = ref(false)

const table = useTable<CacheItem>({
  fetcher: (params) => listCache(collection.value, params.limit, params.offset),
  pageSize: 30,
})

function onSearch() {
  if (!collection.value.trim()) return
  table.refresh()
}

watch(collection, () => {
  if (collection.value && !inputFocused.value) table.refresh()
})

onMounted(async () => {
  // 如果有可用的 collection 自动加载
})
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">缓存数据</h2>
    <div class="panel">
      <div style="display:flex;gap:8px;margin-bottom:12px">
        <el-input
          v-model="collection"
          placeholder="输入 target_collection 名称 (如 httpbin)"
          style="width:360px"
          @focus="inputFocused = true"
          @blur="inputFocused = false"
          @keyup.enter="onSearch"
        />
        <el-button type="primary" @click="onSearch">查询</el-button>
      </div>

      <el-empty v-if="!table.items.value.length && !table.loading.value" description="输入 collection 名称查询缓存" />
      <template v-else>
        <div v-for="d in table.items.value" :key="d.id" style="margin-bottom:8px">
          <div class="cache-meta">id: {{ d.id }} | 时间: {{ formatDateTime(d.created_at) }}</div>
          <pre class="cache-doc">{{ JSON.stringify(d.document, null, 2) }}</pre>
        </div>

        <div v-if="table.total.value > 0" style="display:flex;justify-content:flex-end;margin-top:12px">
          <el-pagination
            :current-page="table.page.value"
            :page-size="table.pageSize.value"
            :total="table.total.value"
            layout="total, prev, pager, next"
            @current-change="table.onPageChange"
          />
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.cache-meta {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}
.cache-doc {
  background: #0d1117;
  color: #c9d1d9;
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  overflow: auto;
  max-height: 400px;
}
</style>