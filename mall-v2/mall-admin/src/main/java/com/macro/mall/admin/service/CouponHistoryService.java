package com.macro.mall.admin.service;

import com.macro.mall.common.CommonPage;
import com.macro.mall.common.CommonResult;
import com.macro.mall.mbg.model.CouponHistory;

import java.util.List;

public interface CouponHistoryService {
    CommonResult<Long> receive(Long couponId, Long memberId);

    CommonResult<Void> use(Long historyId, Long orderId, String orderSn);

    CommonResult<List<CouponHistory>> listByMember(Long memberId, Integer status);

    CommonResult<CommonPage<CouponHistory>> listHistories(Long couponId, Integer pageNum, Integer pageSize);
}
