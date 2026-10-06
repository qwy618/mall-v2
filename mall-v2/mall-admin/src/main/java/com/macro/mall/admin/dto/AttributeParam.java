package com.macro.mall.admin.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

/**
 * 属性定义的增改入参（债务 1）。
 * 属性按分类隔离：同一个"颜色"在 T恤 与 手机通讯 下是两条独立记录。
 */
@Data
public class AttributeParam {
    @NotNull(message = "分类不能为空")
    private Long categoryId;
    @NotBlank(message = "属性名不能为空")
    private String name;
    /** 0规格(SKU级,影响价格库存) 1参数(商品级,仅展示) */
    @NotNull(message = "属性类型不能为空")
    private Integer type;
    /** 录入方式：0手工录入 1从列表选择；不传则按 type 取默认（规格=1，参数=0） */
    private Integer inputType;
    /** type=0 时的候选值清单，逗号分隔，如：黑色,白色 */
    private String inputList;
    private Integer sort;
}
