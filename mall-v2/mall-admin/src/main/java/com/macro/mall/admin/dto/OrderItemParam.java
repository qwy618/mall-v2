package com.macro.mall.admin.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class OrderItemParam {
    @NotNull(message = "SKU不能为空") private Long skuId;
    @NotNull(message = "数量不能为空") private Integer quantity;
}

