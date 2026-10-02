export interface Coupon {
  id: number
  name: string
  amount?: number // 满减 / 立减金额
  minPoint?: number // 满减门槛（0 或空 = 无门槛）
  discount?: number // 折扣券：0~1，如 0.8 表示打 8 折（与 amount 二选一）
  useType?: number // 0=全场通用 1=指定分类 2=指定商品
  categoryId?: number // useType=1 指定分类时生效
  productId?: number // useType=2 指定商品时生效
  perLimit?: number
  publishCount?: number
  receiveCount?: number
  useCount?: number
  startTime?: string
  endTime?: string
  note?: string
}

// status 含义：0=未使用 1=已使用 2=已过期
export interface MyCouponVO {
  coupon: Coupon
  status: number
  createTime?: string
}

// 后端预估：某券对当前订单的可用性与优惠（权威值，前端不再本地计算）
export interface CouponEstimate {
  coupon: Coupon
  usable: boolean // 是否满足适用范围 + 门槛
  baseAmount: number // 券适用商品小计（BigDecimal -> number）
  discount: number // 预计优惠（usable 时 > 0）
  reason?: string // 不可用原因
}
