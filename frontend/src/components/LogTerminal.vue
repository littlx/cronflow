<!--
  LogTerminal — Vercel-style 日志详情。

  设计:
  - 纯黑底 (#000) + 极简标题栏 (无 macOS dots, 取代为状态点 + 标题 + 复制)
  - meta 信息排成两列, 用 "Label  Value" 单色小字
  - 输出区无装饰边条, 仅靠间距与色彩分层
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
  <div v-if="log" class="term">
    <div class="term-head">
      <span :class="['status-dot', log.status]"></span>
      <span class="term-title">
        <span class="muted">log</span>
        <span>#{{ log.id }}</span>
        <span class="sep">·</span>
        <span class="muted">attempt</span>
        <span>{{ log.attempt }}</span>
      </span>
      <button class="copy" @click="copy">复制</button>
    </div>

    <div class="term-body">
      <div class="meta-grid">
        <div class="meta-row"><span class="lbl">任务</span><span class="val">{{ log.task_name }}</span></div>
        <div class="meta-row"><span class="lbl">ref</span><code class="val">{{ log.task_ref }}</code></div>
        <div class="meta-row"><span class="lbl">状态</span><span class="val"><StatusTag :status="log.status" /></span></div>
        <div class="meta-row"><span class="lbl">触发</span><span class="val">{{ triggerLabel(log.trigger_type) }}</span></div>
        <div class="meta-row"><span class="lbl">尝试</span><span class="val">第 {{ log.attempt }} 次</span></div>
        <div class="meta-row"><span class="lbl">耗时</span><span class="val">{{ formatDuration(log.duration) }}</span></div>
        <div class="meta-row"><span class="lbl">开始</span><span class="val">{{ formatDateTime(log.started_at) }}</span></div>
        <div class="meta-row"><span class="lbl">结束</span><span class="val">{{ formatDateTime(log.finished_at) }}</span></div>
      </div>

      <div class="hr"></div>

      <div class="output">
        <template v-if="log.status === 'success'">
          <div class="line ok">✓ Task executed successfully</div>
          <pre class="code">{{ formatContent(log.result) }}</pre>
        </template>
        <template v-else-if="log.status === 'running'">
          <div class="line ok pulse">→ Running — task is still in progress</div>
        </template>
        <template v-else>
          <div class="line err">✗ Task execution failed</div>
          <pre class="code err-text">{{ log.error }}</pre>
          <template v-if="log.result">
            <div class="line ok">→ Partial result</div>
            <pre class="code">{{ formatContent(log.result) }}</pre>
          </template>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.term {
  background: #000;
  border: 1px solid #1a1a1a;
  border-radius: 8px;
  overflow: hidden;
  font-family: 'Geist Mono', 'JetBrains Mono', 'SF Mono', Menlo, Monaco, monospace;
}

.term-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: #0a0a0a;
  border-bottom: 1px solid #1a1a1a;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: #666;
}
.status-dot.success { background: #0a7d27; box-shadow: 0 0 0 3px rgba(10, 125, 39, 0.18); }
.status-dot.failed  { background: #e00; box-shadow: 0 0 0 3px rgba(238, 0, 0, 0.18); }
.status-dot.running { background: #f5a623; box-shadow: 0 0 0 3px rgba(245, 166, 35, 0.18); animation: dot-pulse 1.4s ease-in-out infinite; }
@keyframes dot-pulse {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.4; }
}

.term-title {
  flex: 1;
  font-size: 12px;
  color: #ededed;
  display: flex;
  align-items: center;
  gap: 6px;
}
.term-title .muted { color: #666; }
.term-title .sep { color: #333; margin: 0 2px; }

.copy {
  background: transparent;
  color: #888;
  border: 1px solid #1a1a1a;
  border-radius: 5px;
  padding: 4px 9px;
  font-size: 11px;
  font-family: inherit;
  cursor: pointer;
  transition: all 150ms;
}
.copy:hover {
  color: #fff;
  border-color: #333;
  background: #111;
}

.term-body {
  padding: 16px 18px;
  color: #ededed;
  font-size: 12.5px;
  line-height: 1.65;
  max-height: 520px;
  overflow-y: auto;
}

/* Meta */
.meta-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 24px;
  row-gap: 6px;
}
.meta-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.meta-row .lbl {
  color: #666;
  font-size: 11.5px;
  min-width: 36px;
  flex-shrink: 0;
}
.meta-row .val {
  color: #ededed;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.meta-row code.val {
  color: #79c0ff;
  background: transparent;
  padding: 0;
  font-size: 11.5px;
}

.hr {
  height: 1px;
  background: #1a1a1a;
  margin: 14px 0;
}

.line {
  margin: 4px 0;
  font-size: 12px;
  letter-spacing: -0.01em;
}
.line.ok  { color: #0070f3; }
.line.err { color: #e00; }
.line.pulse { animation: line-pulse 1.6s ease-in-out infinite; }
@keyframes line-pulse {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.45; }
}

.code {
  background: #0a0a0a;
  border: 1px solid #1a1a1a;
  padding: 12px 14px;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 8px 0 14px;
  color: #ededed;
  font-size: 12px;
  line-height: 1.55;
}
.code.err-text { color: #ff6464; }

/* 终端内 scrollbar */
.term-body::-webkit-scrollbar { width: 6px; }
.term-body::-webkit-scrollbar-thumb {
  background: transparent;
  box-shadow: inset 0 0 0 6px rgba(255, 255, 255, 0.1);
  border-radius: 999px;
}
.term-body::-webkit-scrollbar-thumb:hover {
  box-shadow: inset 0 0 0 6px rgba(255, 255, 255, 0.2);
}
</style>