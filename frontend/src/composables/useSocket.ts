/**
 * SocketIO 单例 composable — 跨组件共享一个连接。
 *
 * 解决旧版两个问题:
 * 1) 重连保障: socket.io-client 默认开启自动重连, 这里显式配置策略,
 *    并提供 onConnect/onDisconnect 钩子供 UI 显示连接状态。
 * 2) onUnmounted 清理: 提供 useSocketListener(event, handler), 自动
 *    在组件卸载时 off, 避免重复绑定堆积。
 *
 * 使用:
 *   const socket = useSocket()           // 拿到原始 socket (一般不直接用)
 *   useSocketListener('new_log', handler)// 自动清理的事件监听
 */
import { io, type Socket } from 'socket.io-client'
import { onBeforeUnmount, ref } from 'vue'

let socket: Socket | null = null
const connected = ref(false)

function ensureSocket(): Socket {
  if (!socket) {
    socket = io({
      transports: ['websocket', 'polling'],
      autoConnect: true,
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    })
    socket.on('connect', () => { connected.value = true })
    socket.on('disconnect', () => { connected.value = false })
  }
  return socket
}

export function useSocket(): Socket {
  return ensureSocket()
}

export function useSocketConnected() {
  ensureSocket()
  return connected
}

/**
 * 注册一个 socket 事件监听, 在调用组件卸载时自动 off。
 *
 * 注意: handler 引用必须稳定 (不要在每次 setup 内创建新闭包) — 这里
 * 通过保留 handler 引用并在 unmount 时 off(event, handler) 实现精确清理,
 * 不会误伤其它组件对同一事件的监听。
 */
export function useSocketListener(event: string, handler: (...args: any[]) => void) {
  const s = ensureSocket()
  s.on(event, handler)
  onBeforeUnmount(() => {
    s.off(event, handler)
  })
}
