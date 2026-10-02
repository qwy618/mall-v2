package com.macro.mall.portal.service;

import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.Coupon;
import com.macro.mall.portal.dao.CouponEstimateParam;
import com.macro.mall.portal.vo.CouponEstimateVO;
import com.macro.mall.portal.vo.MyCouponVO;

import java.util.List;

/**
 * C 端优惠券服务。
 * 领券是并发高危操作，核心防护在 impl 的 receive 里用“原子条件更新”实现，见 CouponServiceImpl。
 */
public interface CouponService {

    /** 可领取的优惠券列表（公开，未删除且在有效期内） */
    List<Coupon> listAvailable();

    /**
     * 领取优惠券（防超卖 + 防同会员重复领取）。
     * @param memberId 当前会员ID
     * @param couponId 券模板ID
     */
    CommonResult<Void> receive(Long memberId, Long couponId);

    /** 我的券列表（按领取时间倒序） */
    List<MyCouponVO> myCoupons(Long memberId);

    /**
     * 预估可用券（确认订单页预览，只读不核销）。
     * 与 createOrder 共用 useType / couponBase 规则，保证预览与实扣一致。
     * @param memberId 当前会员ID
     * @param param    订单商品（skuId + quantity）
     */
    List<CouponEstimateVO> estimate(Long memberId, CouponEstimateParam param);
}
