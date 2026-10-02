package com.macro.mall.mbg.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.macro.mall.mbg.model.CouponHistory;
import org.apache.ibatis.annotations.Param;

public interface CouponHistoryMapper extends BaseMapper<CouponHistory>
{
    int useCoupon(@Param("memberId") Long memberId,
                 @Param("couponId") Long couponId,
                 @Param("orderId") Long orderId);
}
