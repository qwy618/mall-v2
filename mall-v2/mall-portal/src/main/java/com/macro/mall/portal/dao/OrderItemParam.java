package com.macro.mall.portal.dao;

import lombok.Data;
import java.io.Serializable;

@Data
public class OrderItemParam implements Serializable {
    private Long skuId;
    private Integer quantity;
    private Long cartItemId; // 可空：购物车结算时填，下单后删除该购物车项
}
