/**
 * 后端 API 数据类型 (与 backend/app/schemas 一一对应)。
 *
 * 字段命名严格保持与后端一致 (snake_case), 避免转换层引入歧义。
 */

export interface TaskParameter {
  name: string
  type: string
  default: unknown
  required: boolean
  description: string
  /** Pydantic BaseModel 参数的完整 JSON Schema */
  schema?: Record<string, unknown> | null
  model_name?: string | null
}

export interface Task {
  ref: string                 // python: 'tasks.x.y' ; curl: 'curl:<uuid>'
  kind: 'python' | 'curl' | string
  name: string
  description: string
  handler_config: Record<string, any>
  parameters: TaskParameter[]
  // curl-only:
  id?: string | null
  created_at?: string | null
  updated_at?: string | null
  // python-only:
  module?: string | null
}

export interface CurlHandlerConfig {
  url: string
  method: string
  headers: Record<string, string>
  params?: Record<string, any> | null
  data: Record<string, any> | string | null
  handler_type: 'PURE_JSON' | 'NESTED_DATA' | 'RAW_RESPONSE'
  target_collection: string
  timeout?: number | null
}

export interface CurlTaskCreate {
  name: string
  description?: string | null
  handler_config: CurlHandlerConfig
}

export interface Schedule {
  id: number
  task_ref: string
  name: string
  trigger_type: 'interval' | 'cron'
  trigger_args: Record<string, any>
  task_args: Record<string, any>
  enabled: boolean
  next_run_time: string | null
  created_at: string | null
  updated_at: string | null
}

export interface ScheduleCreate {
  task_ref: string
  name: string
  trigger_type: 'interval' | 'cron'
  trigger_args: Record<string, any>
  task_args: Record<string, any>
  enabled?: boolean
}

export interface TaskLog {
  id: number
  task_ref: string
  task_name: string
  trigger_type: string
  schedule_id: number | null
  status: 'running' | 'success' | 'failed' | string
  attempt: number
  started_at: string
  finished_at: string | null
  duration: number | null
  result: string | null
  error: string | null
}

export interface Paginated<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface CacheItem {
  id: number
  target_collection: string
  document: Record<string, any> | any[]
  created_at: string | null
}

// ---- 缓存表格视图配置 ----

export type CacheCellType = 'text' | 'number' | 'datetime' | 'boolean' | 'json'

export interface CacheColumnConfig {
  key: string                       // JSON 路径(支持 a.b.c / a[0].b)
  label: string
  type: CacheCellType
  width?: number | null
}

export interface CacheViewConfig {
  target_collection: string
  row_path: string                  // "" 表示 document 自身即行集合
  columns: CacheColumnConfig[]
  created_at?: string | null
  updated_at?: string | null
}

export interface CacheViewConfigUpsert {
  row_path: string
  columns: CacheColumnConfig[]
}

export interface StatsPayload {
  total_tasks: number
  total_schedules: number
  active_schedules: number
  total_runs: number
  success_runs: number
  failed_runs: number
  running_runs: number
  success_rate: number
  system: { cpu_usage: number; memory_usage: number }
  recent_logs: TaskLog[]
}

// ---- 通知 ----

export interface NotificationConfig {
  id: number
  name: string
  channel: string                   // 'webhook' | 未来 'sms' | 'email' | ...
  config: Record<string, any>       // 渠道特定配置
  events: string[]                  // ['task_failed', 'task_success', ...]
  enabled: boolean
  created_at?: string | null
  updated_at?: string | null
}

export interface NotificationConfigCreate {
  name: string
  channel: string
  config: Record<string, any>
  events: string[]
  enabled: boolean
}

export interface NotificationLog {
  id: number
  config_id: number
  event: string
  task_log_id: number | null
  status: 'success' | 'failed' | string
  message: string | null
  created_at: string | null
}

// ---- 监控中心看板配置 ----

export interface DashboardTableConfig {
  collection: string
  width: 'third' | 'half' | 'full'
  visibleColumns: string[]
}

export interface DashboardConfig {
  username: string
  config: DashboardTableConfig[]
  created_at?: string | null
  updated_at?: string | null
}

export interface DashboardConfigUpsert {
  config: DashboardTableConfig[]
}
