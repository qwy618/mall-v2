package com.macro.mall.portal.dao;

import lombok.Data;

import java.util.List;

/**
 * 优惠券预估入参：前端把当前要结算的商品（skuId + 数量）发过来，
 * 后端用真实商品数据计算每个券的适用范围、门槛与优惠。
 */
@Data
public class CouponEstimateParam {
    private List<EstimateItem> items;

    @Data
    public static class EstimateItem {
        private Long skuId;
        private Integer quantity;
    }
}
