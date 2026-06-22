/**
 * 任务相关 API 调用 (python + curl 统一)。
 */
import client from './client'
import type { CurlTaskCreate, Task } from './types'

export function listTasks(kind?: 'python' | 'curl') {
  return client.get<Task[]>('/tasks', { params: kind ? { kind } : {} }).then((r) => r.data)
}

export function getTask(ref: string) {
  return client.get<Task>(`/tasks/${encodeURIComponent(ref)}`).then((r) => r.data)
}

export function createCurlTask(payload: CurlTaskCreate) {
  return client.post<Task>('/tasks/curl', payload).then((r) => r.data)
}

export function updateCurlTask(taskId: string, payload: Partial<CurlTaskCreate>) {
  return client.put<Task>(`/tasks/curl/${taskId}`, payload).then((r) => r.data)
}

export function deleteCurlTask(taskId: string) {
  return client.delete(`/tasks/curl/${taskId}`).then((r) => r.data)
}

export function triggerTask(task_ref: string, task_args: Record<string, any> = {}) {
  return client.post('/tasks/trigger', { task_ref, task_args }).then((r) => r.data)
}
