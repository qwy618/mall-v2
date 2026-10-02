// 后台管理端 WebSocket 客户端：连接 /ws/admin，接收新订单等实时事件。
// 单例模式 + 自动重连；全局只需 startAdminWs() 一次，用 onAdminWsMessage 订阅消息。

type WsMessageHandler = (msg: any) => void

const handlers = new Set<WsMessageHandler>()
let socket: WebSocket | null = null
let started = false
let retries = 0

function buildUrl(): string {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  // 走同源（dev 下经 Vite 代理转发到后端 8080），无需额外配置跨域
  return `${proto}://${location.host}/ws/admin`
}

function connect() {
  const ws = new WebSocket(buildUrl())
  socket = ws
  ws.onopen = () => {
    retries = 0
  }
  ws.onmessage = (ev) => {
    let data: any = null
    try {
      data = JSON.parse(ev.data)
    } catch {
      return
    }
    handlers.forEach((fn) => fn(data))
  }
  ws.onclose = () => {
    retries += 1
    const delay = Math.min(1000 * retries, 10000)
    setTimeout(connect, delay)
  }
  ws.onerror = () => {
    ws.close()
  }
}

export function startAdminWs() {
  if (started) return
  started = true
  connect()
}

export function onAdminWsMessage(fn: WsMessageHandler): () => void {
  handlers.add(fn)
  return () => {
    handlers.delete(fn)
  }
}
