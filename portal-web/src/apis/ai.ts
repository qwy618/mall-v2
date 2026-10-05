/**
 * 智能助手接口层。
 *
 * 流式必须用 fetch + ReadableStream 手写 SSE 解析：
 * EventSource 只支持 GET、且无法带自定义 body，而助手契约是 POST + JSON body（token 在 body 里）。
 */

/** 请求体（与后端 ChatRequest 对齐） */
export interface AiChatBody {
  message: string
  token?: string | null
  session_id?: string
  /** true 时后端把 message 当「系统指令」而非用户发言（用于「已确认下单」触发 place_order） */
  as_system?: boolean
}

/** 事件回调：type 为 SSE 事件名，payload 为已解析的 data 对象 */
export interface AiStreamHandlers {
  onEvent: (type: string, payload: Record<string, unknown>) => void
  /** 网络层/HTTP 层错误（业务错误走 error 事件，不走这里） */
  onError?: (message: string) => void
  /** 流正常结束（无论成功或出错都会回调，便于收尾） */
  onClose?: () => void
}

const AI_BASE = '/ai'

/** 把一个 SSE 事件块（已按空行切分）解析成 (type, obj) */
function parseBlock(block: string): { type: string; obj: Record<string, unknown> } | null {
  const dataLines: string[] = []
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith('data:')) {
      // 规范允许 "data: 值" 或 "data:值"，这里只吃掉一个前导空格
      dataLines.push(line.slice(5).replace(/^ /, ''))
    }
  }
  if (dataLines.length === 0) return null
  const raw = dataLines.join('\n')
  try {
    const obj = JSON.parse(raw) as Record<string, unknown>
    const type = typeof obj.type === 'string' ? obj.type : 'message'
    return { type, obj }
  } catch {
    return null // 半截/脏数据直接丢弃，不能让一轮对话崩掉
  }
}

/**
 * 发起一次流式对话。返回的 Promise 在流结束（或出错）后 resolve。
 * 通过 AbortSignal 支持「停止生成」。
 */
export async function streamChat(
  body: AiChatBody,
  handlers: AiStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const res = await fetch(`${AI_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(body),
      signal,
    })
    if (!res.ok || !res.body) {
      throw new Error(`助手服务不可用（${res.status}）`)
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buf = ''

    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      // 直接剔除 \r：SSE 里 \r 只用于行分隔，data 内容里的换行会被 JSON 转义成 \\r，删不到真数据。
      // 关键：\r 必须在**拼接后的缓冲区**语义下被消除。若只做 \r\n→\n 的成对替换，
      // 一旦 TCP 把 \r\n 拆到两个 chunk（上一个 chunk 正以 \r 结尾），替换就会失效，
      // 缓冲区里留下 \r\n\r\n，而按 \n\n 切块的自检查永远匹配不到 → 事件全部堆积、流结束时报废。
      buf += decoder.decode(value, { stream: true }).replace(/\r/g, '')
      let idx = buf.indexOf('\n\n')
      while (idx >= 0) {
        const block = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        const parsed = parseBlock(block)
        if (parsed) handlers.onEvent(parsed.type, parsed.obj)
        idx = buf.indexOf('\n\n')
      }
    }
    // 收尾：个别实现最后一块可能不带结尾空行
    const tail = parseBlock(buf)
    if (tail) handlers.onEvent(tail.type, tail.obj)
  } catch (e) {
    // 主动中止不算错误
    if (e instanceof DOMException && e.name === 'AbortError') return
    handlers.onError?.(e instanceof Error ? e.message : '网络异常，请稍后重试')
  } finally {
    handlers.onClose?.()
  }
}

/** 清除服务端会话记忆（只清本会话） */
export async function clearChatSession(sessionId: string): Promise<void> {
  await fetch(`${AI_BASE}/chat/clear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
}

/** 拉取会话历史（用于重新进入页面时恢复消息） */
export async function fetchChatHistory(
  sessionId: string,
  token?: string | null,
): Promise<Array<Record<string, unknown>>> {
  const qs = new URLSearchParams({ session_id: sessionId })
  if (token) qs.set('token', token)
  const res = await fetch(`${AI_BASE}/chat/history?${qs.toString()}`)
  if (!res.ok) return []
  const data = (await res.json()) as { messages?: Array<Record<string, unknown>> }
  return data.messages || []
}
