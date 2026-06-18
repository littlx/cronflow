import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

client.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const msg = error.response?.data?.detail || error.message
    return Promise.reject(new Error(msg))
  }
)

export default client
