/** 订单实体：字段严格对齐后端 Order.java（GET /order/list 返回的 JSON）。
 *  BigDecimal 在 Jackson 下序列化为 number，这里用 number 承接；展示时 toFixed(2)。
 *  LocalDateTime 序列化为 ISO 字符串（可空字段用可选属性）。 */
export interface Order {
  id: number
  orderSn: string // 后端生成的唯一订单号（Redis INCR）
  memberId: number
  addressId: number
  totalAmount: number
  payAmount: number
  freightAmount: number
  payType: number // 0 模拟支付
  status: number // 0待付款 1已付款 2已发货 3已完成 4已关闭 5无效订单（作废）
  deleteStatus: number // 全局逻辑删：1 已删
  deliveryCompany?: string
  deliverySn?: string
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

/** 订单项：字段对齐后端 OrderItem.java */
export interface OrderItem {
  id: number
  orderId: number
  orderSn: string
  skuId: number
  skuCode: string
  productId: number
  productName: string
  productPic?: string
  productSn?: string
  spData?: string
  price: number
  quantity: number
  createTime?: string
}

/** 订单详情出参：对应后端 OrderDetailVO（订单 + 订单项列表） */
export interface OrderDetailVO {
  order: Order
  items: OrderItem[]
}

/** 下单入参：对应后端 OrderParam（前端可传字段白名单，禁含 id/status/orderSn 等） */
export interface OrderParam {
  memberId: number
  addressId: number
  items: OrderItemParam[]
  freightAmount?: number
}

/** 下单商品行：对应后端 OrderItemParam */
export interface OrderItemParam {
  skuId: number
  quantity: number
}

/** 发货入参：对应后端 OrderShipParam */
export interface OrderShipParam {
  deliveryCompany: string
  deliverySn: string
}

/** 订单列表查询参数：对应后端 listOrders 的入参（GET 透传） */
export interface OrderListParams {
  pageNum: number
  pageSize: number
  status?: number
  memberId?: number
  keyword?: string
}

/** 订单状态枚举：0待付款 1已付款 2已发货 3已完成 4已关闭 5无效订单（后台作废，已退款） */
export const ORDER_STATUS_TEXT: Record<number, string> = {
  0: '待付款',
  1: '已付款',
  2: '已发货',
  3: '已完成',
  4: '已关闭',
  5: '无效订单',
}

/** 状态对应 el-tag 的颜色类型 */
export const ORDER_STATUS_TAG: Record<number, 'warning' | 'primary' | 'success' | 'info' | 'danger'> = {
  0: 'warning',
  1: 'primary',
  2: 'success',
  3: 'success',
  4: 'info',
  5: 'danger',
}
