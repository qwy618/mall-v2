import request from '@/utils/request'
import type { PageResult } from '@/types/product'
import type {
  Order,
  OrderDetailVO,
  CreateOrderParam,
  OrderPreviewParam,
  OrderPreviewVO,
} from '@/types/order'

// 获取下单幂等令牌（债务23）：一次性，进入确认订单页时取，提交订单时带回
export function generateOrderToken() {
  return request<string>({
    url: '/order/token',
    method: 'post',
  })
}

// 创建订单，返回 orderId（Long）
export function createOrder(param: CreateOrderParam) {
  return request<number>({
    url: '/order/create',
    method: 'post',
    data: param,
  })
}

// 订单试算（金额同源）：与 /order/create 用同一段代码算钱，但无副作用
// （不扣库存/不落库/不消耗幂等令牌），可安全反复调用，供确认订单页展示应付金额
export function previewOrder(param: OrderPreviewParam) {
  return request<OrderPreviewVO>({
    url: '/order/preview',
    method: 'post',
    data: param,
  })
}

// 支付（0->1），返回 orderId
export function payOrder(orderId: number) {
  return request<number>({
    url: '/order/pay',
    method: 'post',
    params: { orderId },
  })
}

// 取消订单（0->4，并还原库存），返回 orderId
export function cancelOrder(orderId: number) {
  return request<number>({
    url: '/order/cancel',
    method: 'post',
    params: { orderId },
  })
}

// 确认收货（2->3），返回 orderId
export function confirmReceived(orderId: number) {
  return request<number>({
    url: '/order/confirmReceived',
    method: 'post',
    params: { orderId },
  })
}

// 我的订单列表（CommonPage<Order>）
export function listOrders(params: { status?: number; pageNum?: number; pageSize?: number }) {
  return request<PageResult<Order>>({
    url: '/order/list',
    method: 'get',
    params,
  })
}

// 订单详情（OrderDetailVO）
export function getOrderDetail(orderId: number) {
  return request<OrderDetailVO>({
    url: '/order/detail',
    method: 'get',
    params: { orderId },
  })
}
