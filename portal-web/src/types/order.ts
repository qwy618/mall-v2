// 订单 / 地址 相关类型，对齐后端 OrderController / AddressController / Order 实体

// 下单入参（后端 CreateOrderParam）
export interface OrderItemParam {
  skuId: number
  quantity: number
  cartItemId?: number | null // 购物车结算时填，下单后删除该购物车项；立即购买为 null
}

export interface CreateOrderParam {
  addressId: number
  items: OrderItemParam[]
  couponId?: number | null // 使用的优惠券（Coupon 模板 id）；不使用则留空/null
  submitToken?: string // 下单幂等令牌（债务23）：进入确认订单页时取号，提交时原样带回
  useIntegration?: number // 本单使用的积分数（债务18）：100 积分 = 1 元，0/不传表示不使用
}

// 订单主表（对齐 Order 实体）
export interface Order {
  id: number
  orderSn?: string
  memberId?: number
  addressId?: number
  totalAmount?: number // BigDecimal -> number
  payAmount?: number
  freightAmount?: number
  couponId?: number // 使用的优惠券模板 id
  couponAmount?: number // 优惠券抵扣金额（BigDecimal -> number）
  promotionAmount?: number // 会员等级折扣金额（债务18）
  useIntegration?: number // 本单使用的积分数（债务18）
  integrationAmount?: number // 积分抵扣金额（债务18，100 积分 = 1 元）
  payType?: number
  status: number // 0待支付 1已支付 2已发货 3已完成 4已取消 5已失效（后台作废）
  deliveryCompany?: string
  deliverySn?: string
  deleteStatus?: number
  receiverName?: string
  receiverPhone?: string
  receiverProvince?: string
  receiverCity?: string
  receiverDistrict?: string
  receiverDetailAddress?: string
  createTime?: string
  paymentTime?: string
  deliveryTime?: string
  receiveTime?: string
  closeTime?: string
  updateTime?: string
}

// 订单明细快照（对齐 OrderItem 实体）
export interface OrderItem {
  id: number
  orderId?: number
  orderSn?: string
  skuId?: number
  skuCode?: string
  productId?: number
  productName?: string
  productPic?: string
  productSn?: string
  spData?: string // 规格 JSON，如 {"颜色":"红","尺码":"L"}
  price?: number
  quantity?: number
  commentStatus?: number // 评价状态 0未评价 1已评价（对应 order_item.comment_status）
  // 分行分摊（债务 7 / 18 落库）：本行承担的各项优惠
  couponAmount?: number // 本行分摊的优惠券金额
  promotionAmount?: number // 本行分摊的会员折扣金额
  integrationAmount?: number // 本行分摊的积分抵扣金额
  // 分摊后实际实付（债务 7 落库），退款严格按此值，杜绝按原价退
  realAmount?: number
  createTime?: string
}

// 订单详情（对齐 OrderDetailVO）
export interface OrderDetailVO {
  order: Order
  items: OrderItem[]
}

// 待支付订单超时时长（毫秒）。须与后端 MqConstants.ORDER_TTL 保持一致（当前 30 分钟）
export const ORDER_PAY_TIMEOUT_MS = 30 * 60 * 1000

// 收货地址（对齐 MemberAddress 实体）
export interface Address {
  id?: number
  memberId?: number
  receiverName: string
  phone: string
  province: string
  city: string
  district: string
  detailAddress: string
  defaultStatus?: number
  createTime?: string
  updateTime?: string
}
