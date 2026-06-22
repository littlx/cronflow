<!--
  LogTerminal — 日志详情弹窗内的终端式展示。
  Dashboard 与 LogsView 共用, 消除旧版的重复代码。

  props:
    - log: TaskLog 对象 (null 时不渲染)

  视觉:
    - 精致的终端式窗口 (macOS traffic light + 渐变标题栏)
    - 结构化 meta 信息 + 语法着色输出
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
    <!-- 标题栏 -->
    <div class="terminal-header">
      <div class="dots">
        <span class="dot red"></span>
        <span class="dot yellow"></span>
        <span class="dot green"></span>
      </div>
      <div class="terminal-title">log #{{ log.id }} · attempt {{ log.attempt }}</div>
      <el-button size="small" class="copy-btn" @click="copy">复制日志</el-button>
    </div>

    <!-- 内容区 -->
    <div class="terminal-body">
      <div class="meta-grid">
        <div class="meta-item">
          <span class="lbl">任务</span>
          <span class="val">{{ log.task_name }}</span>
        </div>
        <div class="meta-item">
          <span class="lbl">ref</span>
          <code class="val">{{ log.task_ref }}</code>
        </div>
        <div class="meta-item">
          <span class="lbl">状态</span>
          <span class="val"><StatusTag :status="log.status" /></span>
        </div>
        <div class="meta-item">
          <span class="lbl">触发</span>
          <span class="val">{{ triggerLabel(log.trigger_type) }}</span>
        </div>
        <div class="meta-item">
          <span class="lbl">尝试</span>
          <span class="val">第 {{ log.attempt }} 次</span>
        </div>
        <div class="meta-item">
          <span class="lbl">耗时</span>
          <span class="val">{{ formatDuration(log.duration) }}</span>
        </div>
        <div class="meta-item">
          <span class="lbl">开始</span>
          <span class="val">{{ formatDateTime(log.started_at) }}</span>
        </div>
        <div class="meta-item">
          <span class="lbl">结束</span>
          <span class="val">{{ formatDateTime(log.finished_at) }}</span>
        </div>
      </div>

      <div class="divider"></div>

      <div class="output">
        <template v-if="log.status === 'success'">
          <div class="line info">→ Task executed successfully</div>
          <pre class="code">{{ formatContent(log.result) }}</pre>
        </template>
        <template v-else-if="log.status === 'running'">
          <div class="line info pulse">⏳ Running — task is still in progress...</div>
        </template>
        <template v-else>
          <div class="line error">✗ Task execution failed</div>
          <pre class="code error-text">{{ log.error }}</pre>
          <template v-if="log.result">
            <div class="line info">→ Partial result</div>
            <pre class="code">{{ formatContent(log.result) }}</pre>
          </template>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ---- Terminal container ---- */
.terminal {
  background: #0d1117;
  border-radius: var(--cf-radius-lg);
  overflow: hidden;
  font-family: 'JetBrains Mono', 'SF Mono', Menlo, Monaco, 'Courier New', monospace;
  border: 1px solid rgba(48, 54, 61, 0.6);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25), inset 0 0 0 1px rgba(255, 255, 255, 0.04);
}

/* ---- Header ---- */
.terminal-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background:
    linear-gradient(180deg, #1c2333 0%, #161b2a 100%);
  border-bottom: 1px solid #30363d;
}
.dots {
  display: flex;
  gap: 7px;
  flex-shrink: 0;
}
.dot {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  transition: opacity 0.15s;
}
.dot.red    { background: #ff5f56; }
.dot.yellow { background: #ffbd2e; }
.dot.green  { background: #27c93f; }

.terminal-title {
  flex: 1;
  font-size: 11.5px;
  color: #8b949e;
  text-align: center;
  letter-spacing: 0.3px;
}
.copy-btn {
  flex-shrink: 0;
  background: rgba(110, 118, 129, 0.15);
  color: #c9d1d9;
  border: 1px solid rgba(110, 118, 129, 0.25);
  border-radius: 6px;
  font-family: inherit;
  height: 26px;
  font-size: 11px;
}
.copy-btn:hover {
  background: rgba(110, 118, 129, 0.25);
  color: #fff;
}

/* ---- Body ---- */
.terminal-body {
  padding: 16px 18px;
  color: #c9d1d9;
  font-size: 12.5px;
  line-height: 1.6;
  max-height: 520px;
  overflow-y: auto;
}

/* Meta grid */
.meta-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 5px 18px;
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
.meta-item .lbl {
  color: #8b949e;
  font-size: 11px;
  min-width: 32px;
  flex-shrink: 0;
}
.meta-item .val {
  color: #e6edf3;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.meta-item code.val {
  color: #79c0ff;
  background: rgba(110, 118, 129, 0.2);
  padding: 0 5px;
  border-radius: 4px;
  font-size: 11.5px;
}

/* Divider */
.divider {
  border: none;
  border-top: 1px solid #21262d;
  margin: 14px 0;
}

/* Output */
.line {
  margin: 4px 0;
  font-size: 12px;
}
.line.info  { color: #7ee787; }
.line.error { color: #f85149; font-weight: 500; }
.line.pulse  { animation: cf-pulse-text 1.6s ease-in-out infinite; }

@keyframes cf-pulse-text {
  0%, 100% { opacity: 0.9; }
  50%      { opacity: 0.4; }
}

.code {
  background: rgba(110, 118, 129, 0.07);
  padding: 12px 14px;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 6px 0 12px;
  color: #d2d8e0;
  font-size: 12px;
  line-height: 1.5;
  border-left: 2px solid #30363d;
}
.code.error-text {
  color: #ffa198;
  border-left-color: #f85149;
}

/* Terminal 内部 scrollbar */
.terminal-body::-webkit-scrollbar { width: 6px; }
.terminal-body::-webkit-scrollbar-thumb {
  background: rgba(48, 54, 61, 0.6);
  border-radius: 999px;
}
.terminal-body::-webkit-scrollbar-thumb:hover { background: rgba(48, 54, 61, 0.8); }
</style>