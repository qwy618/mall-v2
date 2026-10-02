package com.macro.mall.admin.service;

import com.macro.mall.admin.dto.CouponParam;
import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.Coupon;
import jakarta.validation.Valid;

public interface CouponService {
    CommonResult<CommonPage<Coupon>> listCoupons(Integer pageNum, Integer pageSize, Integer useType, String keyword);

    CommonResult<Coupon> detail(Long id);

    CommonResult<Long> createCoupon(@Valid CouponParam param);

    CommonResult<Integer> updateCoupon(Long id, @Valid CouponParam param);

    CommonResult<Integer> deleteCoupon(Long id);
}
