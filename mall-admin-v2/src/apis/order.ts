import request from '@/utils/request'
import type { Order, OrderDetailVO, OrderParam, OrderItemParam, OrderShipParam, OrderListParams } from '@/types/order'
import type { CommonPage } from '@/types/common'

/**
 * 分页查询订单列表：GET /order/list
 * 支持筛选：keyword（订单号模糊）、status（0待付款 1已付款 2已发货 3已完成 4已关闭）、memberId
 * 后端 listOrders 用 LambdaQueryWrapper 按需拼接，MP 自动过滤 delete_status=0（已删不显示）。
 */
export function listOrders(params: OrderListParams): Promise<CommonPage<Order>> {
  return request<CommonPage<Order>>({
    url: '/order/list',
    method: 'get',
    params,
  })
}

/** 订单详情：GET /order/{id}，返回 CommonResult<OrderDetailVO>（order + items） */
export function getOrderDetail(id: number): Promise<OrderDetailVO> {
  return request<OrderDetailVO>({
    url: `/order/${id}`,
    method: 'get',
  })
}

/** 模拟下单：POST /order/create，后端返回新增订单 id（Redis 生成订单号 + 乐观扣库存） */
export function createOrder(data: OrderParam): Promise<number> {
  return request<number>({
    url: '/order/create',
    method: 'post',
    data,
  })
}

/** 支付：POST /order/pay/{id}，状态 0→1，返回订单 id */
export function payOrder(id: number): Promise<number> {
  return request<number>({
    url: `/order/pay/${id}`,
    method: 'post',
  })
}

/** 发货：POST /order/ship/{id}，状态 1→2，需传物流公司/单号 */
export function shipOrder(id: number, data: OrderShipParam): Promise<number> {
  return request<number>({
    url: `/order/ship/${id}`,
    method: 'post',
    data,
  })
}

/** 确认收货：POST /order/complete/{id}，状态 2→3，返回订单 id */
export function completeOrder(id: number): Promise<number> {
  return request<number>({
    url: `/order/complete/${id}`,
    method: 'post',
  })
}

/** 取消订单：POST /order/cancel/{id}，状态 0→4，并逐 item 还原库存，返回订单 id */
export function cancelOrder(id: number): Promise<number> {
  return request<number>({
    url: `/order/cancel/${id}`,
    method: 'post',
  })
}

/**
 * 作废订单：POST /order/invalidate/{id}，状态 1→5（无效订单）。
 * 用于"已付款但无法履约"（如发货前商品下架/缺货）：后端会回滚库存、退优惠券、
 * 退回抵扣积分并写退款流水。仅已付款未发货可作废。
 */
export function invalidateOrder(id: number, note?: string): Promise<number> {
  return request<number>({
    url: `/order/invalidate/${id}`,
    method: 'post',
    params: { note },
  })
}

/** 删除订单（逻辑删）：POST /order/delete/{id}，返回影响行数 */
export function deleteOrder(id: number): Promise<number> {
  return request<number>({
    url: `/order/delete/${id}`,
    method: 'post',
  })
}

// 仅类型导出（供视图层构造入参时使用）
export type { OrderItemParam }
