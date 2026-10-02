package com.macro.mall.portal.vo;

import com.macro.mall.mbg.model.Coupon;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 我的券：优惠券模板 + 领取记录状态。
 * status 沿用 coupon_history：0=未使用 1=已使用 2=已过期
 */
@Data
public class MyCouponVO {
    private Coupon coupon;
    private Integer status;
    private LocalDateTime createTime;
}
