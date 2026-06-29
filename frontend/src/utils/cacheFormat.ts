/**
 * 缓存表格视图 — 数据访问与格式化工具。
 *
 * - getByPath: 在嵌套对象/数组上按字符串路径取值, 支持 'a.b.c' 与 'a[0].b' 形式
 * - inferRows: 从 document 推断「行集合」, 返回 {rowPath, rows}
 * - discoverPaths: 在示例行上扫描叶子节点路径 (深度受限, 数组里的对象会下钻一层)
 * - formatCellValue: 根据列 type 把原始值转成可显示字符串
 */
import type { CacheCellType } from '@/api/types'
import { formatPlainDateTime } from './format'

/** 解析 a.b[0].c 形式的路径为段数组。 */
function parsePath(path: string): (string | number)[] {
  if (!path) return []
  const segs: (string | number)[] = []
  // 支持 a.b.c / a[0].b / a.b[0][1]
  const re = /[^.[\]]+|\[(\d+)\]/g
  let m: RegExpExecArray | null
  while ((m = re.exec(path)) !== null) {
    if (m[1] !== undefined) segs.push(Number(m[1]))
    else segs.push(m[0])
  }
  return segs
}

export function getByPath(obj: unknown, path: string): unknown {
  if (obj == null) return undefined
  if (!path) return obj
  const segs = parsePath(path)
  let cur: any = obj
  for (const s of segs) {
    if (cur == null) return undefined
    cur = cur[s as any]
  }
  return cur
}

/** 推断行集合: 数组 → 自身; 对象 → 找最长数组字段; 否则 → 单行。 */
export function inferRows(document: unknown): { rowPath: string; rows: unknown[] } {
  if (Array.isArray(document)) return { rowPath: '', rows: document }
  if (document && typeof document === 'object') {
    // 在两层内寻找最长的数组字段
    let best: { path: string; len: number } | null = null
    const walk = (node: any, prefix: string, depth: number) => {
      if (depth > 2 || node == null || typeof node !== 'object') return
      for (const k of Object.keys(node)) {
        const v = node[k]
        const p = prefix ? `${prefix}.${k}` : k
        if (Array.isArray(v)) {
          if (!best || v.length > best.len) best = { path: p, len: v.length }
        } else if (v && typeof v === 'object') {
          walk(v, p, depth + 1)
        }
      }
    }
    walk(document, '', 0)
    if (best) {
      const rows = getByPath(document, (best as { path: string }).path)
      if (Array.isArray(rows)) return { rowPath: (best as { path: string }).path, rows }
    }
    // 没找到数组字段, 把单对象当一行
    return { rowPath: '', rows: [document] }
  }
  return { rowPath: '', rows: [document] }
}

/** 扫描示例行的叶子路径 (用于列字段自动发现下拉)。 */
export function discoverPaths(sampleRow: unknown, maxDepth = 2): string[] {
  const out: string[] = []
  const visit = (node: any, prefix: string, depth: number) => {
    if (node == null) {
      if (prefix) out.push(prefix)
      return
    }
    if (typeof node !== 'object') {
      if (prefix) out.push(prefix)
      return
    }
    if (Array.isArray(node)) {
      // 数组本身作为一个叶子可选项, 用户可选 json 类型查看
      if (prefix) out.push(prefix)
      return
    }
    if (depth >= maxDepth) {
      if (prefix) out.push(prefix)
      return
    }
    for (const k of Object.keys(node)) {
      const p = prefix ? `${prefix}.${k}` : k
      visit(node[k], p, depth + 1)
    }
  }
  visit(sampleRow, '', 0)
  // 去重 + 稳定排序
  return Array.from(new Set(out))
}

function toNumber(v: unknown): number | null {
  if (v == null || v === '') return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

/** 单元格渲染: 把任意值按 type 转成字符串。空值统一返回 '-'。 */
export function formatCellValue(value: unknown, type: CacheCellType): string {
  if (value == null || value === '') return '-'
  switch (type) {
    case 'number': {
      const n = toNumber(value)
      return n == null ? String(value) : n.toLocaleString()
    }
    case 'datetime': {
      // 支持 ISO 字符串 / Unix 秒 / 毫秒
      if (typeof value === 'number') {
        const ms = value > 1e12 ? value : value * 1000
        return formatPlainDateTime(new Date(ms).toISOString())
      }
      if (typeof value === 'string') {
        // 全数字串当时间戳
        if (/^\d+$/.test(value)) {
          const num = Number(value)
          const ms = num > 1e12 ? num : num * 1000
          return formatPlainDateTime(new Date(ms).toISOString())
        }
        return formatPlainDateTime(value)
      }
      return String(value)
    }
    case 'boolean': {
      if (typeof value === 'boolean') return value ? '✔' : '✘'
      if (value === 'true' || value === 1 || value === '1') return '✔'
      if (value === 'false' || value === 0 || value === '0') return '✘'
      return String(value)
    }
    case 'json': {
      try {
        return JSON.stringify(value)
      } catch {
        return String(value)
      }
    }
    case 'text':
    default: {
      if (typeof value === 'object') {
        try {
          return JSON.stringify(value)
        } catch {
          return String(value)
        }
      }
      return String(value)
    }
  }
}
