package com.macro.mall.portal.dao;

import com.macro.mall.portal.dao.OrderItemParam;
import lombok.Data;
import java.io.Serializable;
import java.util.List;

@Data
public class CreateOrderParam implements Serializable {
    private Long addressId;
    private Integer couponId;
    private List<OrderItemParam> items;
    /** 下单幂等令牌（债务23）：进入确认订单页时由 /order/token 获取，提交时原样带回 */
    private String submitToken;
    /** 本单使用的积分数（债务18）：100 积分 = 1 元，不传/0 表示不使用 */
    private Integer useIntegration;
}
