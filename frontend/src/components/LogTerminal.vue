<!--
  LogTerminal — 日志详情弹窗内的终端式展示。
  Dashboard 与 LogsView 共用, 消除旧版的重复代码。

  props:
    - log: TaskLog 对象 (null 时不渲染)
-->
<script setup lang="ts">
import { ElMessage } from 'element-plus'
import type { TaskLog } from '@/api/types'
import StatusTag from './StatusTag.vue'
import { formatDateTime, formatDuration } from '@/utils/format'

const props = defineProps<{ log: TaskLog | null }>()

function formatContent(val: any): string {
  if (val == null || val === '') return 'No output returned.'
  if (typeof val === 'object') return JSON.stringify(val, null, 2)
  try {
    const parsed = JSON.parse(val)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return String(val)
  }
}

function triggerLabel(t: string): string {
  return { interval: '间隔', cron: 'Cron', manual: '手动' }[t] || t
}

async function copy() {
  if (!props.log) return
  const log = props.log
  const text = log.status === 'success'
    ? `[INFO] Task executed successfully. Return value:\n${formatContent(log.result)}`
    : `[ERROR] Task execution failed:\n${log.error}${log.result ? `\n\n[INFO] Partial result:\n${formatContent(log.result)}` : ''}`
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('日志已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}
</script>

<template>
  <div v-if="log" class="terminal">
    <div class="terminal-header">
      <div class="dots">
        <span class="dot red"></span>
        <span class="dot yellow"></span>
        <span class="dot green"></span>
      </div>
      <div class="title">log #{{ log.id }} - attempt {{ log.attempt }}</div>
      <el-button size="small" plain @click="copy">复制日志</el-button>
    </div>
    <div class="terminal-body">
      <div class="meta">
        <div><span class="lbl">任务:</span> {{ log.task_name }}</div>
        <div><span class="lbl">ref:</span> <code>{{ log.task_ref }}</code></div>
        <div><span class="lbl">状态:</span> <StatusTag :status="log.status" /></div>
        <div><span class="lbl">触发:</span> {{ triggerLabel(log.trigger_type) }}</div>
        <div><span class="lbl">尝试:</span> 第 {{ log.attempt }} 次</div>
        <div><span class="lbl">耗时:</span> {{ formatDuration(log.duration) }}</div>
        <div><span class="lbl">开始:</span> {{ formatDateTime(log.started_at) }}</div>
        <div><span class="lbl">结束:</span> {{ formatDateTime(log.finished_at) }}</div>
      </div>
      <hr class="divider" />
      <div class="output">
        <template v-if="log.status === 'success'">
          <div class="line info">[INFO] Task executed successfully. Return value:</div>
          <pre class="code">{{ formatContent(log.result) }}</pre>
        </template>
        <template v-else-if="log.status === 'running'">
          <div class="line info">[RUNNING] Task is still in progress...</div>
        </template>
        <template v-else>
          <div class="line error">[ERROR] Task execution failed:</div>
          <pre class="code error-text">{{ log.error }}</pre>
          <template v-if="log.result">
            <div class="line info">[INFO] Partial result:</div>
            <pre class="code">{{ formatContent(log.result) }}</pre>
          </template>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.terminal {
  background: #0d1117;
  border-radius: 8px;
  overflow: hidden;
  font-family: 'SF Mono', Menlo, Monaco, 'Courier New', monospace;
}
.terminal-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: #21262d;
  border-bottom: 1px solid #30363d;
}
.dots {
  display: flex;
  gap: 6px;
}
.dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}
.dot.red { background: #ff5f56; }
.dot.yellow { background: #ffbd2e; }
.dot.green { background: #27c93f; }
.title {
  flex: 1;
  font-size: 12px;
  color: #c9d1d9;
  text-align: center;
}
.terminal-body {
  padding: 14px 16px;
  color: #c9d1d9;
  font-size: 12.5px;
  max-height: 480px;
  overflow-y: auto;
}
.meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 16px;
  color: #c9d1d9;
}
.meta .lbl {
  color: #8b949e;
  margin-right: 6px;
}
.meta code {
  color: #79c0ff;
  background: rgba(110, 118, 129, 0.2);
  padding: 1px 4px;
  border-radius: 3px;
}
.divider {
  border: none;
  border-top: 1px solid #30363d;
  margin: 12px 0;
}
.line {
  margin: 4px 0;
}
.line.info { color: #7ee787; }
.line.error { color: #f85149; }
.code {
  background: rgba(110, 118, 129, 0.1);
  padding: 10px 12px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 4px 0 10px;
  color: #c9d1d9;
}
.code.error-text {
  color: #ffa198;
}
</style>
