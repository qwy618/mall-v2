package com.macro.mall.portal.vo;

import com.macro.mall.mbg.model.Coupon;
import lombok.Data;

import java.math.BigDecimal;

/**
 * 优惠券预估（确认订单页预览用）。
 * 仅计算“能用哪张、能减多少”，不真正核销券、不扣库存。
 * 与 createOrder 共用 useType / couponBase 规则，保证预览与实扣一致。
 */
@Data
public class CouponEstimateVO {
    private Coupon coupon;          // 券模板（前端取 id / name / 描述）
    private boolean usable;         // 时间有效 + 达到适用范围门槛
    private BigDecimal baseAmount;  // 券适用商品小计（全场=整单；指定分类=该类之和；指定商品=该商品之和）
    private BigDecimal discount;    // 预估优惠（仅 usable 时 > 0）；= min(券额, baseAmount)
    private String reason;          // 不可用原因
}
