package com.macro.mall.admin.dto;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.math.BigDecimal;

@Data
public class SkuParam {
    @NotNull(message = "商品ID不能为空")
    private Long productId;
    private String spData;                       // 规格 JSON，可空
    @NotNull(message = "价格不能为空")
    @DecimalMin(value = "0.01", message = "价格必须大于0")
    private BigDecimal price;
    private Integer stock;
    private Integer lockStock;
    private String pic;
    private Integer sale;
}
