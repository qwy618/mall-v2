package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

/**
 * SKU 规格值：SKU 级、影响价格库存（对应 product_attribute.type=0）。
 * 由 sku.sp_data 拆解派生而来（sp_data 仍是真源），用于「按规格筛选」走 idx_attr_value。
 * 例：某 SKU 的"颜色=黑色"。
 */
@Data
@TableName("sku_attribute_value")
public class SkuAttributeValue {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private Long skuId;            // sku_id 关联 sku.id
    private Long attributeId;      // attribute_id 关联 product_attribute.id(type=0)
    private String value;          // 该 SKU 在这个属性上的取值，如：黑色
}
