import request from '@/utils/request'
import type { Coupon, MyCouponVO, CouponEstimate } from '@/types/coupon'

export function listCoupons() {
  return request<Coupon[]>({
    url: '/coupon/list',
    method: 'get',
  })
}

export function receiveCoupon(couponId: number) {
  return request<null>({
    url: '/coupon/receive',
    method: 'post',
    params: { couponId },
  })
}

export function myCoupons() {
  return request<MyCouponVO[]>({
    url: '/coupon/my',
    method: 'get',
  })
}

// 预估可用券：前端只传订单商品（skuId+quantity），后端用真实商品数据
// 计算每张券的适用范围(couponBase)、门槛与优惠，返回权威预估结果。
export function estimateCoupons(items: { skuId: number; quantity: number }[]) {
  return request<CouponEstimate[]>({
    url: '/coupon/estimate',
    method: 'post',
    data: { items },
  })
}
