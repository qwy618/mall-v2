import request from '@/utils/request'
import type { ReturnApplyEntity, ReturnApplyParam } from '@/types/return'

/**
 * 申请退货：POST /return/apply（会员 JWT 鉴权）
 * 后端按 order_item.real_amount 计算退款金额，杜绝按原价退。
 */
export function applyReturn(data: ReturnApplyParam) {
  return request<number>({
    url: '/return/apply',
    method: 'post',
    data,
  })
}

/**
 * 我的退货申请列表：GET /return/list
 * 注意：后端返回 List（非分页），直接渲染数组即可。
 */
export function listReturns() {
  return request<ReturnApplyEntity[]>({
    url: '/return/list',
    method: 'get',
  })
}

/**
 * 退货申请详情：GET /return/detail/{id}
 * 返回实体，proofPics / returnItems 为 JSON 字符串，需前端 JSON.parse。
 */
export function getReturnDetail(id: number) {
  return request<ReturnApplyEntity>({
    url: `/return/detail/${id}`,
    method: 'get',
  })
}

/**
 * 会员回填退货物流单号：POST /return/shipBack/{id}?returnTrackingNo=xxx
 */
export function shipBackReturn(id: number, returnTrackingNo: string) {
  return request<number>({
    url: `/return/shipBack/${id}`,
    method: 'post',
    params: { returnTrackingNo },
  })
}
