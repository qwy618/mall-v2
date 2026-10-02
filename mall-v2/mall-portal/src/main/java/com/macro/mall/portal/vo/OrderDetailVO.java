package com.macro.mall.portal.vo;

import com.macro.mall.mbg.model.Order;
import com.macro.mall.mbg.model.OrderItem;
import lombok.Data;

import java.util.List;

@Data
public class OrderDetailVO {
    private Order order;
    private List<OrderItem> items;
}
