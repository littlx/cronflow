<script setup lang="ts">
import { ref, onMounted } from 'vue'
import client from '@/api/client'
import { ElMessage } from 'element-plus'

interface CurlTask {
  id: string
  name: string
  minutes: number
  is_enabled: boolean
  handler_type: string
  target_collection: string
  request_config: { url: string; method: string; headers: any; data: any }
  status: string
  last_run_result: string | null
  error_message: string | null
}

const tasks = ref<CurlTask[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const previewCollection = ref<string>('')
const previewData = ref<any[]>([])
const previewVisible = ref(false)

const form = ref({
  name: '',
  minutes: 5,
  is_enabled: true,
  handler_type: 'PURE_JSON',
  target_collection: '',
  url: '',
  method: 'GET',
  headers: '{}',
  data: '',
})

async function load() {
  loading.value = true
  try { const { data } = await client.get('/curl-tasks'); tasks.value = data }
  finally { loading.value = false }
}

async function submit() {
  let headers = {}
  try { headers = JSON.parse(form.value.headers || '{}') } catch { ElMessage.error('headers 不是合法 JSON'); return }
  let payloadData: any = null
  if (form.value.data) {
    try { payloadData = JSON.parse(form.value.data) } catch { ElMessage.error('data 不是合法 JSON'); return }
  }
  try {
    await client.post('/curl-tasks', {
      name: form.value.name,
      minutes: form.value.minutes,
      is_enabled: form.value.is_enabled,
      handler_type: form.value.handler_type,
      target_collection: form.value.target_collection,
      request_config: { url: form.value.url, method: form.value.method, headers, data: payloadData },
    })
    ElMessage.success('已创建')
    dialogVisible.value = false
    load()
  } catch (e: any) { ElMessage.error(e.message) }
}

async function trigger(t: CurlTask) {
  try { await client.post(`/curl-tasks/${t.id}/trigger`); ElMessage.success('已触发') }
  catch (e: any) { ElMessage.error(e.message) }
}

async function preview(t: CurlTask) {
  previewCollection.value = t.target_collection
  try {
    const { data } = await client.get(`/curl-tasks/data/${t.target_collection}`)
    previewData.value = data
    previewVisible.value = true
  } catch (e: any) { ElMessage.error(e.message) }
}

async function remove(t: CurlTask) {
  try { await client.delete(`/curl-tasks/${t.id}`); ElMessage.success('已删除'); load() }
  catch (e: any) { ElMessage.error(e.message) }
}

onMounted(load)
</script>

<template>
  <h2 class="page-title">数据同步</h2>
  <div class="panel">
    <div style="margin-bottom:12px">
      <el-button type="primary" @click="dialogVisible = true">+ 新建同步任务</el-button>
    </div>
    <el-empty v-if="!tasks.length" description="暂无同步任务" />
    <el-table v-else :data="tasks" v-loading="loading" size="small">
      <el-table-column prop="name" label="名称" min-width="120" />
      <el-table-column label="URL" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">{{ row.request_config.url }}</template>
      </el-table-column>
      <el-table-column prop="minutes" label="间隔(分)" width="90" />
      <el-table-column prop="target_collection" label="缓存表" width="120" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_enabled?'success':'info'" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="trigger(row)">触发</el-button>
          <el-button size="small" @click="preview(row)">预览缓存</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>

  <el-dialog v-model="dialogVisible" title="新建同步任务" width="560px">
    <el-form label-width="100px">
      <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
      <el-form-item label="URL"><el-input v-model="form.url" placeholder="https://..." /></el-form-item>
      <el-form-item label="方法">
        <el-select v-model="form.method" style="width:120px">
          <el-option v-for="m in ['GET','POST','PUT','DELETE']" :key="m" :label="m" :value="m" />
        </el-select>
      </el-form-item>
      <el-form-item label="间隔(分钟)"><el-input-number v-model="form.minutes" :min="1" /></el-form-item>
      <el-form-item label="缓存表名"><el-input v-model="form.target_collection" placeholder="my_api_data" /></el-form-item>
      <el-form-item label="处理方式">
        <el-select v-model="form.handler_type" style="width:200px">
          <el-option label="纯JSON" value="PURE_JSON" />
          <el-option label="嵌套data" value="NESTED_DATA" />
          <el-option label="原始响应" value="RAW_RESPONSE" />
        </el-select>
      </el-form-item>
      <el-form-item label="Headers"><el-input v-model="form.headers" type="textarea" :rows="2" /></el-form-item>
      <el-form-item label="Body(JSON)"><el-input v-model="form.data" type="textarea" :rows="3" /></el-form-item>
      <el-form-item label="启用"><el-switch v-model="form.is_enabled" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="submit">创建</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="previewVisible" :title="`缓存预览: ${previewCollection}`" width="720px">
    <el-empty v-if="!previewData.length" description="暂无缓存数据" />
    <div v-else style="max-height:480px;overflow:auto">
      <pre v-for="(d,i) in previewData" :key="i" style="background:#0d1117;padding:10px;border-radius:6px;margin-bottom:8px;font-size:12px">{{ JSON.stringify(d.document, null, 2) }}</pre>
    </div>
  </el-dialog>
</template>
