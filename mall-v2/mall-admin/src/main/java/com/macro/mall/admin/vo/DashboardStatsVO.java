package com.macro.mall.admin.vo;

import lombok.Data;

@Data
public class DashboardStatsVO {
    private Long productTotal;     // 商品总数（product 物理删，全量）
    private Long orderTotal;       // 订单总数（orders 逻辑删，MP 自动过滤）
    private Long orderToday;       // 今日订单数（create_time >= 今日 0 点）
    private Long brandTotal;       // 品牌数（逻辑删）
    private Long categoryTotal;    // 分类数（逻辑删）
    private Long couponTotal;      // 优惠券总数（逻辑删）
    private Long couponReceived;   // 优惠券已领取（coupon_history 全量）
    private Long couponUsed;       // 优惠券已使用（coupon_history status=1）
}
