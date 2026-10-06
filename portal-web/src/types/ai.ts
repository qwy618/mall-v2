/**
 * 智能助手（mall-ai-agent）前端类型：与 SSE 事件契约一一对应。
 * 契约来源：mall-ai-agent/app/main.py → /api/chat/stream
 */

/** 商品卡片（后端 main._card() 的字段子集；price 可能为 null） */
export interface AiProduct {
  id: number
  name: string
  price?: number | null
  pic?: string
  subTitle?: string
  reason?: string // 猜你喜欢：推荐理由
}

/** 加购成功卡 */
export interface AiCartAdded {
  cartId?: number
  productName: string
  price?: number | null
  quantity?: number | null
}

/** 订单确认卡里的商品行 */
export interface AiConfirmItem {
  name: string
  pic?: string
  price?: number | null
  quantity?: number | null
  promotion?: string
}

/** 订单确认卡（preview_order 生成草稿后的展示数据） */
export interface AiConfirm {
  draftId: string
  addressText: string
  items: AiConfirmItem[]
  totalAmount?: number | null
  promotionAmount?: number | null
  payAmount?: number | null
}

/** 下单成功卡 */
export interface AiOrder {
  orderId: number
  orderSn?: string
  payAmount?: number | null
}

/**
 * 引用项（M3.4）：助手回答「使用体验 / 口碑」类问题时，命中的商品信息来源。
 *
 * ⚠️ `source === 'product_profile'`（商品档案）的条目 **没有评价数据** ——
 * `starAvg` / `reviewCount` 会是 `null`，渲染前必须判空，否则会显示「0.0 分 · 0 条评价」。
 */
export interface AiCitation {
  productId: number
  name: string
  /** 来源：product_profile（商品档案）/ review_summary（已购评价聚合） */
  source?: string
  starAvg?: number | null
  reviewCount?: number | null
}

/** 助手消息里的一个片段：按 SSE 事件到达顺序拼装，保证「文字 / 卡片」的先后顺序不乱 */
export type AiPart =
  | { kind: 'text'; text: string }
  | { kind: 'tool'; name: string; args?: string }
  | { kind: 'products'; items: AiProduct[] }
  | { kind: 'product'; item: AiProduct }
  | { kind: 'cart'; data: AiCartAdded }
  | { kind: 'confirm'; data: AiConfirm }
  | { kind: 'order'; data: AiOrder }
  | { kind: 'citation'; items: AiCitation[] }

/** 一条聊天消息（前端 UI 模型，非后端存储结构） */
export interface AiMsg {
  id: string
  role: 'user' | 'assistant'
  parts: AiPart[]
  /** 正在流式接收中（用于显示光标/禁用输入） */
  streaming?: boolean
  /** 出错标记（气泡变浅红提示） */
  error?: boolean
}

/** SSE 事件名（与后端一致） */
export type AiEventType =
  | 'token'
  | 'tool'
  | 'products'
  | 'product'
  | 'cart_added'
  | 'confirm'
  | 'order'
  | 'citation'
  | 'need_login'
  | 'done'
  | 'error'
