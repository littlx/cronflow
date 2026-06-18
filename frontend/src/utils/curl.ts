/**
 * curl 命令解析 — 把 `curl 'URL' -H '...' -d '...'` 解析成表单可用的结构。
 *
 * 参照原项目 DataSyncManager.vue 的正则分词方案:
 * 1. 去掉行尾续行反斜杠
 * 2. 用正则切出 token (单引号串 / 双引号串 / 裸词)
 * 3. 顺序消费 -X / -H / -d / --data-raw / --data-binary 等选项
 */

export interface ParsedCurl {
  url: string
  method: string
  headers: Record<string, string>
  /** 解析后的请求体: 优先 JSON object, 其次 form-urlencoded object, 最后原始字符串 */
  data: Record<string, any> | string | null
  /** 原始 data 字符串 (便于前端判断) */
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

/** 判断一个 token 是否像 URL */
function looksLikeUrl(s: string): boolean {
  return /^https?:\/\//i.test(s) || /^www\./i.test(s)
}

/**
 * 解析 curl 命令字符串。失败抛 Error(可读消息)。
 */
export function parseCurl(command: string): ParsedCurl {
  if (!command || !command.trim()) {
    throw new Error('命令为空')
  }

  // 去掉行尾续行符 + 前导 shell 提示符
  const cleanCurl = command.replace(/\\\r?\n/g, ' ').replace(/^\s*\$+\s*/, '').trim()

  // 分词: 单引号串 / 双引号串 / 裸词
  const regex = /'([^']*)'|"([^"]*)"|([^\s'"]+)/g
  const tokens: string[] = []
  let m: RegExpExecArray | null
  while ((m = regex.exec(cleanCurl)) !== null) {
    tokens.push(m[1] ?? m[2] ?? m[3] ?? '')
  }

  if (!tokens.length) throw new Error('命令为空')

  // 跳过开头的 curl
  let start = 0
  if (tokens[0] === 'curl' || tokens[0].endsWith('/curl')) start = 1

  const result: ParsedCurl = {
    url: '',
    method: 'GET',
    headers: {},
    data: null,
    rawData: '',
  }

  let hasData = false

  for (let i = start; i < tokens.length; i++) {
    const part = tokens[i]

    // 处理 --opt=value 形式
    if (part.startsWith('--') && part.includes('=')) {
      const eq = part.indexOf('=')
      const key = part.slice(0, eq)
      const val = part.slice(eq + 1)
      if (key === '--data' || key === '--data-raw' || key === '--data-binary' || key === '--data-ascii' || key === '--data-urlencode') {
        result.rawData = result.rawData ? result.rawData + '&' + val : val
        hasData = true
      } else if (key === '--header' || key === '-H') {
        applyHeader(result.headers, val)
      } else if (key === '--request' || key === '-X') {
        result.method = val.toUpperCase()
      } else if (key === '--json') {
        result.rawData = result.rawData ? result.rawData + '&' + val : val
        hasData = true
        if (!hasHeader(result.headers, 'Content-Type')) {
          result.headers['Content-Type'] = 'application/json'
        }
      } else if (key === '--user-agent' || key === '-A') {
        if (!hasHeader(result.headers, 'User-Agent')) result.headers['User-Agent'] = val
      } else if (key === '--cookie' || key === '-b') {
        if (!hasHeader(result.headers, 'Cookie')) result.headers['Cookie'] = val
      } else if (key === '--referer' || key === '-e') {
        if (!hasHeader(result.headers, 'Referer')) result.headers['Referer'] = val
      }
      // 其它 --x=y 忽略
      continue
    }

    // 粘连短选项: -XGET / -H'K:V'
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

    // 需要取下一个 token 的值选项
    if (VALUE_OPTS.has(part)) {
      const next = tokens[++i]
      if (next === undefined) throw new Error(`选项 ${part} 缺少值`)
      // 容错: 跳过孤立的 shell 提示符 $
      const val = next === '$' ? tokens[++i] : next
      if (part === '-X' || part === '--request') {
        result.method = val.toUpperCase()
      } else if (part === '-H' || part === '--header') {
        applyHeader(result.headers, val)
      } else if (
        part === '-d' || part === '--data' || part === '--data-raw' ||
        part === '--data-binary' || part === '--data-ascii' || part === '--data-urlencode'
      ) {
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

    // 以 - 开头的未知选项: 忽略当前 token
    if (part.startsWith('-') && part.length > 1) continue

    // 位置参数 → URL
    if (!result.url && (looksLikeUrl(part) || !part.startsWith('-'))) {
      result.url = part
    } else if (!result.url) {
      result.url = part
    }
  }

  if (!result.url) throw new Error('未能从 cURL 中解析出 URL')

  // method 兜底: 有 body 默认 POST
  if (hasData && result.method === 'GET') result.method = 'POST'

  // 解析 data
  if (hasData && result.rawData) {
    const ct = getHeader(result.headers, 'Content-Type') || ''
    // 优先 JSON
    if (result.rawData.trim().startsWith('{') || result.rawData.trim().startsWith('[') || ct.includes('json')) {
      try {
        result.data = JSON.parse(result.rawData)
      } catch {
        result.data = result.rawData
      }
    } else if (ct.includes('form-urlencoded') || result.rawData.includes('=')) {
      // form-urlencoded → object
      try {
        const params = new URLSearchParams(result.rawData)
        const obj: Record<string, string> = {}
        params.forEach((v, k) => (obj[k] = v))
        result.data = obj
      } catch {
        result.data = result.rawData
      }
    } else {
      result.data = result.rawData
    }
  }

  return result
}

function applyHeader(headers: Record<string, string>, raw: string): void {
  const colon = raw.indexOf(':')
  if (colon > -1) {
    headers[raw.slice(0, colon).trim()] = raw.slice(colon + 1).trim()
  }
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
  try {
    headers['Authorization'] = 'Basic ' + btoa(userpass)
  } catch {
    headers['Authorization'] = 'Basic ' + userpass
  }
}
