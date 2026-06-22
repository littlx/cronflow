<!--
  NotificationsView — 通知配置 + 发送记录。
  - 配置 tab: webhook URL / 订阅事件 (task_failed / task_success) / 启停 / 测试
  - 记录 tab: 分页查询 NotificationLog
-->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import * as notifApi from '@/api/notifications'
import { useTable } from '@/composables/useTable'
import StatusTag from '@/components/StatusTag.vue'
import { formatDateTime } from '@/utils/format'
import type { NotificationConfig, NotificationLog } from '@/api/types'

const activeTab = ref<'configs' | 'logs'>('configs')

// ---- 配置列表 ----
const configs = ref<NotificationConfig[]>([])
const configsLoading = ref(false)

async function loadConfigs() {
  configsLoading.value = true
  try {
    configs.value = await notifApi.listConfigs()
  } finally {
    configsLoading.value = false
  }
}

// ---- 新建/编辑配置 ----
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)

interface FormState {
  name: string
  channel: 'webhook' | string
  url: string
  method: 'POST' | 'GET' | 'PUT'
  headersJson: string
  timeout: number | null
  events: string[]            // ['task_failed', 'task_success']
  enabled: boolean
}

const empty = (): FormState => ({
  name: '', channel: 'webhook', url: '', method: 'POST',
  headersJson: '{}', timeout: 10, events: ['task_failed'], enabled: true,
})
const form = ref<FormState>(empty())

function openCreate() {
  editingId.value = null
  form.value = empty()
  dialogVisible.value = true
}

function openEdit(c: NotificationConfig) {
  editingId.value = c.id
  form.value = {
    name: c.name,
    channel: c.channel,
    url: c.config?.url || '',
    method: c.config?.method || 'POST',
    headersJson: JSON.stringify(c.config?.headers || {}, null, 2),
    timeout: c.config?.timeout ?? 10,
    events: c.events?.length ? [...c.events] : ['task_failed'],
    enabled: c.enabled,
  }
  dialogVisible.value = true
}

async function submit() {
  if (!form.value.name) { ElMessage.error('名称必填'); return }
  if (form.value.channel === 'webhook' && !form.value.url) {
    ElMessage.error('webhook 必须填写 URL'); return
  }
  let headers: Record<string, string> = {}
  try { headers = JSON.parse(form.value.headersJson || '{}') }
  catch { ElMessage.error('headers 不是合法 JSON'); return }

  const payload = {
    name: form.value.name,
    channel: form.value.channel,
    config: form.value.channel === 'webhook'
      ? { url: form.value.url, method: form.value.method, headers, timeout: form.value.timeout }
      : {},
    events: form.value.events,
    enabled: form.value.enabled,
  }
  try {
    if (editingId.value) {
      await notifApi.updateConfig(editingId.value, payload)
      ElMessage.success('已更新')
    } else {
      await notifApi.createConfig(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    loadConfigs()
  } catch (e: any) {
    ElMessage.error(e.message)
  }
}

async function remove(c: NotificationConfig) {
  try {
    await ElMessageBox.confirm(`删除通知配置 "${c.name}"?`, '确认', { type: 'warning' })
    await notifApi.deleteConfig(c.id)
    ElMessage.success('已删除')
    loadConfigs()
  } catch { /* cancel */ }
}

async function toggleEnabled(c: NotificationConfig) {
  try {
    await notifApi.updateConfig(c.id, { enabled: !c.enabled })
    ElMessage.success(c.enabled ? '已禁用' : '已启用')
    loadConfigs()
  } catch (e: any) { ElMessage.error(e.message) }
}

async function sendTest(c: NotificationConfig) {
  try {
    await notifApi.testConfig(c.id)
    ElMessage.success('测试通知已发送')
  } catch (e: any) {
    ElMessage.error('测试失败: ' + e.message)
  }
}

// ---- 发送记录 ----
const logTable = useTable<NotificationLog>({
  fetcher: (params) => notifApi.listLogs(params),
  pageSize: 50,
})

onMounted(() => {
  loadConfigs()
  logTable.load()
})
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">通知</h2>
    <div class="panel">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="通知配置" name="configs">
          <div style="margin-bottom:14px">
            <el-button type="primary" :icon="Plus" @click="openCreate">新建通知</el-button>
          </div>
          <el-empty v-if="!configs.length" description="暂无通知配置 — 新建一个 webhook 来接收任务失败/成功事件" />
          <el-table v-else :data="configs" v-loading="configsLoading" size="small">
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column prop="channel" label="渠道" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ row.channel }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="URL / 配置" min-width="260" show-overflow-tooltip>
              <template #default="{ row }">{{ row.config?.url || JSON.stringify(row.config) }}</template>
            </el-table-column>
            <el-table-column label="订阅事件" min-width="200">
              <template #default="{ row }">
                <el-tag v-for="ev in row.events" :key="ev" size="small" style="margin-right:4px">{{ ev }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-switch :model-value="row.enabled" @change="toggleEnabled(row)" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" link @click="sendTest(row)">测试</el-button>
                <el-button size="small" type="primary" link @click="openEdit(row)">编辑</el-button>
                <el-button size="small" type="danger" link @click="remove(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="发送记录" name="logs">
          <el-empty v-if="!logTable.items.value.length && !logTable.loading.value" description="暂无通知发送记录" />
          <el-table v-else :data="logTable.items.value" v-loading="logTable.loading.value" size="small">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="config_id" label="配置 ID" width="100" />
            <el-table-column prop="event" label="事件" width="140" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }"><StatusTag :status="row.status" /></template>
            </el-table-column>
            <el-table-column prop="task_log_id" label="关联日志" width="100" />
            <el-table-column prop="message" label="详情" min-width="240" show-overflow-tooltip />
            <el-table-column label="时间" min-width="180">
              <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
            </el-table-column>
          </el-table>
          <div v-if="logTable.total.value > 0" style="display:flex;justify-content:flex-end;margin-top:12px">
            <el-pagination
              :current-page="logTable.page.value"
              :page-size="logTable.pageSize.value"
              :total="logTable.total.value"
              layout="total, prev, pager, next"
              @current-change="logTable.onPageChange"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 新建/编辑配置 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑通知配置' : '新建通知配置'"
      width="600px"
      destroy-on-close
    >
      <el-form label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="例如: 失败告警-飞书机器人" />
        </el-form-item>
        <el-form-item label="渠道">
          <el-select v-model="form.channel" style="width:200px">
            <el-option label="Webhook" value="webhook" />
            <!-- 未来 sms/email/dingtalk/wecom 在此追加 -->
          </el-select>
        </el-form-item>
        <template v-if="form.channel === 'webhook'">
          <el-form-item label="URL" required>
            <el-input v-model="form.url" placeholder="https://hooks.example.com/..." />
          </el-form-item>
          <el-form-item label="方法">
            <el-select v-model="form.method" style="width:120px">
              <el-option v-for="m in ['POST','GET','PUT']" :key="m" :label="m" :value="m" />
            </el-select>
          </el-form-item>
          <el-form-item label="超时(秒)">
            <el-input-number v-model="form.timeout" :min="1" :max="120" />
          </el-form-item>
          <el-form-item label="Headers">
            <el-input v-model="form.headersJson" type="textarea" :rows="2" />
          </el-form-item>
        </template>
        <el-form-item label="订阅事件">
          <el-checkbox-group v-model="form.events">
            <el-checkbox value="task_failed">任务失败</el-checkbox>
            <el-checkbox value="task_success">任务成功</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">{{ editingId ? '更新' : '创建' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>