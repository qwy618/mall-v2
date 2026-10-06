package com.macro.mall.service.vo;

import lombok.Data;

/**
 * 一条属性键值对（admin 与 portal 共用的统一口径）。
 * 用于商品参数（type=1）的读写，也用于规格选项的展示。
 */
@Data
public class AttributeItemVO {
    /** 属性定义ID（product_attribute.id）；写参数时必填，读规格选项时可能为 null */
    private Long attributeId;
    /** 属性名，如：颜色 / 屏幕尺寸 */
    private String name;
    /** 属性值，如：黑色 / 6.7英寸 */
    private String value;
}
