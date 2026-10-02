package com.macro.mall.portal.dao;

import lombok.Data;

@Data
public class ApplyItem {
    private Long orderItemId;   // 退哪个订单项
    private Integer quantity;   // 退几件（≤ 该行购买数量）
}
