/** 优惠券实体：字段严格对齐后端 GET /coupon/list 返回的 JSON（Coupon 表） */
export interface Coupon {
  id: number
  name: string
  /** 面额（优惠金额），BigDecimal 在 JSON 中序列化为 number */
  amount: number
  /** 使用门槛（满 minPoint 元可用），0 表示无门槛 */
  minPoint: number
  /** 适用类型：0 全场通用 / 1 指定分类 / 2 指定商品 */
  useType: number
  categoryId?: number // useType=1 时有效
  productId?: number // useType=2 时有效
  perLimit: number // 每人限领数量
  publishCount: number // 发行量
  receiveCount: number // 已领取数
  useCount: number // 已使用数
  startTime?: string // LocalDateTime → ISO 字符串 "2026-09-17T18:03:24"
  endTime?: string
  note?: string
  createTime?: string
  deleteStatus?: number // 全局逻辑删标记
}

/** 新增/修改优惠券的入参，对应后端 CouponParam（前端可传字段白名单） */
export interface CouponParam {
  name: string
  amount: number
  minPoint?: number
  useType: number
  categoryId?: number
  productId?: number
  perLimit: number
  publishCount: number
  startTime?: string
  endTime?: string
  note?: string
}

/** 优惠券领取记录：对应后端 CouponHistory 表 */
export interface CouponHistory {
  id: number
  couponId: number
  memberId: number // 会员 ID（阶段8 由 admin 模拟）
  couponCode?: string
  orderId?: number
  orderSn?: string
  /** 状态：0 未使用 / 1 已使用 / 2 已过期 */
  status: number
  createTime?: string
  useTime?: string
}

/** 适用类型文案映射 */
export const COUPON_USE_TYPE_TEXT: Record<number, string> = {
  0: '全场通用',
  1: '指定分类',
  2: '指定商品',
}

/** 领取记录状态文案映射 */
export const COUPON_HISTORY_STATUS_TEXT: Record<number, string> = {
  0: '未使用',
  1: '已使用',
  2: '已过期',
}
