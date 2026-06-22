import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 统一错误归一: detail 优先, 否则用 message。后端 422 detail 可能是数组/对象, 一并 stringify。
client.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const detail = error.response?.data?.detail
    let msg: string
    if (typeof detail === 'string') {
      msg = detail
    } else if (detail) {
      try { msg = JSON.stringify(detail) } catch { msg = String(detail) }
    } else {
      msg = error.message || '请求失败'
    }
    return Promise.reject(new Error(msg))
  }
)

export default client
