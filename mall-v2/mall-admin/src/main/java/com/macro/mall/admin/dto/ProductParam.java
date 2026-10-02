package com.macro.mall.admin.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class ProductParam {
    @NotBlank(message = "商品名称不能为空") private String name;
    private String subTitle;
    private String pic;
    @NotNull
    private Long brandId;
    @NotNull private Long categoryId;
    private Integer status;   // 不传则后端默认 1
}
