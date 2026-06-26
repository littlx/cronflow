/**
 * curl 命令解析 — 把 `curl 'URL' -H '...' -d '...'` 解析成表单可用结构。
 *
 * 解析步骤:
 * 1) 去掉行尾续行反斜杠 / 前导 shell 提示符
 * 2) 正则切出 token (单引号串 / 双引号串 / 裸词)
 * 3) 顺序消费 -X / -H / -d / --data-raw / --data-binary 等选项
 */

export interface ParsedCurl {
  url: string                                 // 已剥离 query 的纯 URL
  method: string
  headers: Record<string, string>
  params: Record<string, string>              // 从 URL query 解析出的键值; GET 任务尤其有用
  data: Record<string, any> | string | null
  rawData: string
}

const VALUE_OPTS = new Set([
  '-X', '--request',
  '-H', '--header',
  '-d', '--data', '--data-raw', '--data-binary', '--data-ascii', '--data-urlencode',
  '-A', '--user-agent',
  '-b', '--cookie',
  '-e', '--referer',
  '-u', '--user',
  '--json',
])

function looksLikeUrl(s: string): boolean {
  return /^https?:\/\//i.test(s) || /^www\./i.test(s)
}

export function parseCurl(command: string): ParsedCurl {
  if (!command || !command.trim()) throw new Error('命令为空')

  const cleanCurl = command.replace(/\\\r?\n/g, ' ').replace(/^\s*\$+\s*/, '').trim()

  const regex = /'([^']*)'|"([^"]*)"|([^\s'"]+)/g
  const tokens: string[] = []
  let m: RegExpExecArray | null
  while ((m = regex.exec(cleanCurl)) !== null) {
    tokens.push(m[1] ?? m[2] ?? m[3] ?? '')
  }
  if (!tokens.length) throw new Error('命令为空')

  let start = 0
  if (tokens[0] === 'curl' || tokens[0].endsWith('/curl')) start = 1

  const result: ParsedCurl = { url: '', method: 'GET', headers: {}, params: {}, data: null, rawData: '' }
  let hasData = false

  for (let i = start; i < tokens.length; i++) {
    const part = tokens[i]

    if (part.startsWith('--') && part.includes('=')) {
      const eq = part.indexOf('=')
      const key = part.slice(0, eq)
      const val = part.slice(eq + 1)
      if (['--data', '--data-raw', '--data-binary', '--data-ascii', '--data-urlencode'].includes(key)) {
        result.rawData = result.rawData ? result.rawData + '&' + val : val
        hasData = true
      } else if (key === '--header') {
        applyHeader(result.headers, val)
      } else if (key === '--request') {
        result.method = val.toUpperCase()
      } else if (key === '--json') {
        result.rawData = result.rawData ? result.rawData + '&' + val : val
        hasData = true
        if (!hasHeader(result.headers, 'Content-Type')) result.headers['Content-Type'] = 'application/json'
      } else if (key === '--user-agent') {
        if (!hasHeader(result.headers, 'User-Agent')) result.headers['User-Agent'] = val
      } else if (key === '--cookie') {
        if (!hasHeader(result.headers, 'Cookie')) result.headers['Cookie'] = val
      } else if (key === '--referer') {
        if (!hasHeader(result.headers, 'Referer')) result.headers['Referer'] = val
      }
      continue
    }

    if (/^-[XHdAbeu].+/i.test(part) && !part.startsWith('--')) {
      const flag = part.slice(0, 2)
      const val = part.slice(2)
      if (flag === '-X') result.method = val.toUpperCase()
      else if (flag === '-H') applyHeader(result.headers, val)
      else if (flag === '-d') { result.rawData = result.rawData ? result.rawData + '&' + val : val; hasData = true }
      else if (flag === '-A' && !hasHeader(result.headers, 'User-Agent')) result.headers['User-Agent'] = val
      else if (flag === '-b' && !hasHeader(result.headers, 'Cookie')) result.headers['Cookie'] = val
      else if (flag === '-e' && !hasHeader(result.headers, 'Referer')) result.headers['Referer'] = val
      else if (flag === '-u') setBasicAuth(result.headers, val)
      continue
    }

    if (VALUE_OPTS.has(part)) {
      const next = tokens[++i]
      if (next === undefined) throw new Error(`选项 ${part} 缺少值`)
      const val = next === '$' ? tokens[++i] : next
      if (part === '-X' || part === '--request') {
        result.method = val.toUpperCase()
      } else if (part === '-H' || part === '--header') {
        applyHeader(result.headers, val)
      } else if (['-d', '--data', '--data-raw', '--data-binary', '--data-ascii', '--data-urlencode'].includes(part)) {
        result.rawData = result.rawData ? result.rawData + '&' + val : val
        hasData = true
      } else if (part === '--json') {
        result.rawData = result.rawData ? result.rawData + '&' + val : val
        hasData = true
        if (!hasHeader(result.headers, 'Content-Type')) result.headers['Content-Type'] = 'application/json'
      } else if (part === '-A' || part === '--user-agent') {
        if (!hasHeader(result.headers, 'User-Agent')) result.headers['User-Agent'] = val
      } else if (part === '-b' || part === '--cookie') {
        if (!hasHeader(result.headers, 'Cookie')) result.headers['Cookie'] = val
      } else if (part === '-e' || part === '--referer') {
        if (!hasHeader(result.headers, 'Referer')) result.headers['Referer'] = val
      } else if (part === '-u' || part === '--user') {
        setBasicAuth(result.headers, val)
      }
      continue
    }

    // 可忽略的布尔/开关选项
    if (
      ['-i', '--include', '-v', '--verbose', '-s', '--silent', '--show-error',
       '-L', '--location', '--location-trusted', '-k', '--insecure', '--compressed',
       '-G', '--get', '-f', '--fail', '--fail-with-body', '-N', '--no-buffer', '--raw',
       '--no-progress-meter', '--http1.1', '--http2'].includes(part)
    ) {
      continue
    }

    if (part.startsWith('-') && part.length > 1) continue

    if (!result.url && (looksLikeUrl(part) || !part.startsWith('-'))) {
      result.url = part
    } else if (!result.url) {
      result.url = part
    }
  }

  if (!result.url) throw new Error('未能从 cURL 中解析出 URL')

  // 拆 URL 上的 query 到 params, 保留干净的 URL。
  // 这样 GET 任务在表单里能直接看到 / 编辑参数; 后端 handler 会把 params
  // 再拼回去, 跟原行为等价但更直观。
  result.url = extractQueryToParams(result.url, result.params)

  if (hasData && result.method === 'GET') result.method = 'POST'

  if (hasData && result.rawData) {
    const ct = getHeader(result.headers, 'Content-Type') || ''
    if (result.rawData.trim().startsWith('{') || result.rawData.trim().startsWith('[') || ct.includes('json')) {
      try { result.data = JSON.parse(result.rawData) } catch { result.data = result.rawData }
    } else if (ct.includes('form-urlencoded') || result.rawData.includes('=')) {
      try {
        const params = new URLSearchParams(result.rawData)
        const obj: Record<string, string> = {}
        params.forEach((v, k) => (obj[k] = v))
        result.data = obj
      } catch { result.data = result.rawData }
    } else {
      result.data = result.rawData
    }
  }

  return result
}

function applyHeader(headers: Record<string, string>, raw: string): void {
  const colon = raw.indexOf(':')
  if (colon > -1) headers[raw.slice(0, colon).trim()] = raw.slice(colon + 1).trim()
}

function hasHeader(headers: Record<string, string>, name: string): boolean {
  const ln = name.toLowerCase()
  return Object.keys(headers).some((k) => k.toLowerCase() === ln)
}

function getHeader(headers: Record<string, string>, name: string): string | undefined {
  const ln = name.toLowerCase()
  return Object.entries(headers).find(([k]) => k.toLowerCase() === ln)?.[1]
}

function setBasicAuth(headers: Record<string, string>, userpass: string): void {
  if (hasHeader(headers, 'Authorization')) return
  try { headers['Authorization'] = 'Basic ' + btoa(userpass) }
  catch { headers['Authorization'] = 'Basic ' + userpass }
}

/**
 * 把 URL 上的 ?a=b&c=d 拆到 params, 返回不带 query 的 URL。
 * 同名 key 出现多次时按最后一个胜出 (与表单 key-value 模型一致)。
 *
 * 兼容三种形态:
 *   1. 完整 URL  https://x/y?a=1
 *   2. 协议相对  //x/y?a=1
 *   3. 仅路径    /y?a=1
 */
function extractQueryToParams(
  rawUrl: string,
  params: Record<string, string>,
): string {
  const qIdx = rawUrl.indexOf('?')
  if (qIdx < 0) return rawUrl

  const base = rawUrl.slice(0, qIdx)
  const query = rawUrl.slice(qIdx + 1)
  // hash 不拼回 params, 保留到 URL 末尾
  const hashIdx = query.indexOf('#')
  const pure = hashIdx >= 0 ? query.slice(0, hashIdx) : query
  const hash = hashIdx >= 0 ? '#' + query.slice(hashIdx + 1) : ''

  try {
    const sp = new URLSearchParams(pure)
    sp.forEach((v, k) => {
      if (k) params[k] = v
    })
  } catch {
    return rawUrl
  }
  return base + hash
}

/**
 * 把任务的配置反向生成为 curl 命令
 */
export function stringifyToCurl(cfg: {
  url: string
  method: string
  headers?: Record<string, string>
  params?: Record<string, any>
  data?: any
}): string {
  let fullUrl = cfg.url || ''
  if (cfg.params && Object.keys(cfg.params).length > 0) {
    const q = new URLSearchParams()
    for (const [k, v] of Object.entries(cfg.params)) {
      if (k && v !== undefined && v !== null) {
        q.append(k, String(v))
      }
    }
    const queryString = q.toString()
    if (queryString) {
      fullUrl += (fullUrl.includes('?') ? '&' : '?') + queryString
    }
  }

  let cmd = `curl '${fullUrl}'`
  if (cfg.method && cfg.method.toUpperCase() !== 'GET') {
    cmd += ` -X ${cfg.method.toUpperCase()}`
  }

  if (cfg.headers) {
    for (const [k, v] of Object.entries(cfg.headers)) {
      cmd += ` -H '${k}: ${v}'`
    }
  }

  if (cfg.data) {
    let dataStr = ''
    if (typeof cfg.data === 'string') {
      dataStr = cfg.data
    } else {
      dataStr = JSON.stringify(cfg.data)
    }
    if (dataStr) {
      const escapedData = dataStr.replace(/'/g, "'\\''")
      cmd += ` -d '${escapedData}'`
    }
  }

  return cmd
}

