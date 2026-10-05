package com.macro.mall.portal.dao;

import lombok.Data;

import java.io.Serializable;
import java.util.List;

/**
 * 订单试算入参（债务：金额同源）。
 *
 * <p>与 {@link CreateOrderParam} 的差异：**不含 submitToken**。试算不消耗幂等令牌、
 * 不落库、不扣库存，只是"下单前的金额预演"。
 *
 * <p>addressId 可空：为空时后端取该会员的默认收货地址（AI 助手确认卡片常用此模式）。
 */
@Data
public class OrderPreviewParam implements Serializable {
    /** 收货地址 id，可空（空则取默认地址） */
    private Long addressId;
    /** 优惠券 id，可空 */
    private Integer couponId;
    /** 待试算的商品行（skuId + quantity + 可选 cartItemId） */
    private List<OrderItemParam> items;
    /** 本单拟使用的积分数（100 积分 = 1 元），不传/0 表示不使用 */
    private Integer useIntegration;
}
