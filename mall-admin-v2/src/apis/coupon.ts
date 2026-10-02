import request from '@/utils/request'
import type { Coupon, CouponParam, CouponHistory } from '@/types/coupon'
import type { CommonPage } from '@/types/common'

/** 优惠券分页查询参数：GET /coupon/list */
export interface CouponListParams {
  pageNum: number
  pageSize: number
  useType?: number
  keyword?: string
}

// ==================== Coupon（优惠券主体） ====================
/** 分页查询优惠券：GET /coupon/list，MP 自动过滤 delete_status=0 */
export function listCoupon(params: CouponListParams): Promise<CommonPage<Coupon>> {
  return request<CommonPage<Coupon>>({
    url: '/coupon/list',
    method: 'get',
    params,
  })
}

/** 优惠券详情：GET /coupon/{id} */
export function getCouponDetail(id: number): Promise<Coupon> {
  return request<Coupon>({
    url: `/coupon/${id}`,
    method: 'get',
  })
}

/** 新增优惠券：POST /coupon/create，后端返回新增后的 id */
export function createCoupon(data: CouponParam): Promise<number> {
  return request<number>({
    url: '/coupon/create',
    method: 'post',
    data,
  })
}

/** 修改优惠券：POST /coupon/update/{id}，返回影响行数 */
export function updateCoupon(id: number, data: CouponParam): Promise<number> {
  return request<number>({
    url: `/coupon/update/${id}`,
    method: 'post',
    data,
  })
}

/** 删除优惠券：POST /coupon/delete/{id}，走全局逻辑删，返回影响行数 */
export function deleteCoupon(id: number): Promise<number> {
  return request<number>({
    url: `/coupon/delete/${id}`,
    method: 'post',
  })
}

// ==================== CouponHistory（领取/核销记录） ====================
/**
 * 模拟领取：POST /couponHistory/receive（@RequestParam，POST 走 query 串）
 * 阶段8 是运营后台模拟领取，真实 C 端领券的并发防护留待 mall-portal。
 */
export function receiveCoupon(couponId: number, memberId: number): Promise<number> {
  return request<number>({
    url: '/couponHistory/receive',
    method: 'post',
    params: { couponId, memberId },
  })
}

/**
 * 核销：POST /couponHistory/use（@RequestParam，POST 走 query 串）
 * 把某条"未使用"记录核销为"已使用"，并同步 coupon.use_count+1（同事务）。
 */
export function useCoupon(historyId: number, orderId: number, orderSn: string): Promise<void> {
  return request<void>({
    url: '/couponHistory/use',
    method: 'post',
    params: { historyId, orderId, orderSn },
  })
}

/** 某会员的领取记录：GET /couponHistory/listByMember，status 可选筛选 */
export function listCouponHistoryByMember(
  memberId: number,
  status?: number
): Promise<CouponHistory[]> {
  return request<CouponHistory[]>({
    url: '/couponHistory/listByMember',
    method: 'get',
    params: { memberId, status },
  })
}

/** 某券的全部领取记录（分页）：GET /couponHistory/list */
export function listCouponHistories(
  couponId: number,
  pageNum: number,
  pageSize: number
): Promise<CommonPage<CouponHistory>> {
  return request<CommonPage<CouponHistory>>({
    url: '/couponHistory/list',
    method: 'get',
    params: { couponId, pageNum, pageSize },
  })
}
