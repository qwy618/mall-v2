package com.macro.mall.admin.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.math.BigDecimal;
import java.util.List;

@Data
public class OrderParam {
    @NotNull(message = "会员ID不能为空") private Long memberId;
    @NotNull(message = "地址ID不能为空") private Long addressId;
    @NotNull(message = "订单项不能为空") private List<OrderItemParam> items;
    private BigDecimal freightAmount; // 可选，默认 0
}
