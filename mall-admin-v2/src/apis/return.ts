import request from '@/utils/request'
import type { CommonPage } from '@/types/common'
import type { ReturnApplyEntity } from '@/types/return'

/**
 * 售后申请列表：GET /order/return/list（分页 CommonPage，按状态筛）
 */
export function listReturnApplies(params: { status?: number; pageNum: number; pageSize: number }) {
  return request<CommonPage<ReturnApplyEntity>>({
    url: '/order/return/list',
    method: 'get',
    params,
  })
}

/**
 * 售后申请详情：GET /order/return/{id}
 * 返回实体，proofPics / returnItems 为 JSON 字符串，需前端 JSON.parse。
 */
export function getReturnApplyDetail(id: number) {
  return request<ReturnApplyEntity>({
    url: `/order/return/${id}`,
    method: 'get',
  })
}

/**
 * 同意退货：POST /order/return/approve/{id}?handleNote=&companyAddress=
 * 注意：后端是 @RequestParam，必须用 params 传，不能用 data(body)。
 */
export function approveReturn(id: number, handleNote: string, companyAddress: string) {
  return request<number>({
    url: `/order/return/approve/${id}`,
    method: 'post',
    params: { handleNote, companyAddress },
  })
}

/** 拒绝退货：POST /order/return/reject/{id}?handleNote= */
export function rejectReturn(id: number, handleNote: string) {
  return request<number>({
    url: `/order/return/reject/${id}`,
    method: 'post',
    params: { handleNote },
  })
}

/** 确认收货：POST /order/return/receive/{id} */
export function receiveReturn(id: number) {
  return request<number>({
    url: `/order/return/receive/${id}`,
    method: 'post',
  })
}

/** 完成退款：POST /order/return/complete/{id}?handleNote= */
export function completeReturn(id: number, handleNote: string) {
  return request<number>({
    url: `/order/return/complete/${id}`,
    method: 'post',
    params: { handleNote },
  })
}
