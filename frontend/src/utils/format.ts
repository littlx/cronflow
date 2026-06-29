/**
 * 时间/格式工具 — 后端时间字段统一为 ISO 字符串 (UTC), 前端按 UTC+8 (北京时间) 展示。
 *
 * 通过 Intl.DateTimeFormat 或手动偏移 +8h 实现, 不依赖浏览器时区设置。
 */

/** UTC ISO → Date (UTC+8 时区) */
function toUTC8(iso: string): Date {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return d
  // 把 UTC 时刻转为 UTC+8 本地时刻的同名数字 (不依赖浏览器时区)
  const utcMs = d.getTime()
  return new Date(utcMs + 8 * 3600 * 1000)
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '-'
  try {
    const d = toUTC8(iso)
    if (isNaN(d.getTime())) return iso
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
      d.getHours()
    )}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  } catch {
    return iso
  }
}

/** 距离 target 还有多久, 用于「下次运行」等场景。 */
export function timeUntil(iso: string | null | undefined): string {
  if (!iso) return '-'
  const target = new Date(iso).getTime()
  const now = Date.now()
  const diff = target - now
  if (isNaN(diff)) return '-'
  if (diff <= 0) return '即将执行'

  const secs = Math.floor(diff / 1000)
  const mins = Math.floor(secs / 60)
  const hours = Math.floor(mins / 60)
  const days = Math.floor(hours / 24)

  if (days > 0) return `${days}天后`
  if (hours > 0) return `${hours}小时后`
  if (mins > 0) return `${mins}分钟后`
  return `${secs}秒后`
}

/** 持续时间秒数 → 人类可读 */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '-'
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`
  if (seconds < 60) return `${seconds.toFixed(2)}s`
  const m = Math.floor(seconds / 60)
  const s = (seconds % 60).toFixed(1)
  return `${m}m${s}s`
}

/** 标准时间格式化 — 不做任何人为时区偏移处理，只做日期对象转换和格式化（适用于第三方数据） */
export function formatPlainDateTime(iso: string | null | undefined): string {
  if (!iso) return '-'
  try {
    let parsedIso = iso
    if (iso.includes(' ') && !iso.includes('T')) {
      parsedIso = iso.replace(' ', 'T')
    }
    const d = new Date(parsedIso)
    if (isNaN(d.getTime())) return iso
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
      d.getHours()
    )}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  } catch {
    return iso
  }
}
