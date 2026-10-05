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

// 订单试算入参（后端 OrderPreviewParam）：与 CreateOrderParam 的区别是**不含 submitToken**
// —— 试算不落库、不扣库存、不消耗幂等令牌，只是"下单前的金额预演"
export interface OrderPreviewParam {
  addressId?: number | null // 收货地址，可空（空则后端取该会员默认地址）
  couponId?: number | null // 优惠券模板 id，可空
  items: OrderItemParam[]
  useIntegration?: number // 拟使用的积分数，0/不传表示不使用
}

// 试算行明细（后端 OrderPreviewVO.PreviewItem）：金额分摊与下单同源
export interface OrderPreviewItem {
  skuId?: number
  productId?: number
  productName?: string
  productPic?: string // 取图口径优先 SKU 图，无图回退商品图
  spData?: string // 规格 JSON
  price?: number
  quantity?: number
  lineAmount?: number // 本行原价小计
  promotionAmount?: number // 本行分摊会员折扣
  couponAmount?: number // 本行分摊优惠券
  integrationAmount?: number // 本行分摊积分抵扣
  realAmount?: number // 本行分摊后实付
}

// 订单试算结果（后端 OrderPreviewVO）：每个金额都由下单用的同一段代码计算，故逐分一致
export interface OrderPreviewVO {
  address?: Address | null
  items?: OrderPreviewItem[]
  totalAmount?: number
  freightAmount?: number
  promotionAmount?: number // 会员等级折扣金额
  couponAmount?: number // 优惠券抵扣金额
  integrationAmount?: number // 积分抵扣金额
  useIntegration?: number // 后端按「余额 + 券后应付」封顶后实际可用的积分数
  payAmount?: number
  levelName?: string | null
  discountRate?: number | null // 会员折扣率（%）：100 = 原价
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
