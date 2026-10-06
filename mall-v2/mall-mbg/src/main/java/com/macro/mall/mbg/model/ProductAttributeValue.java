package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

/**
 * 商品参数值：商品级、仅展示、不影响价格库存（对应 product_attribute.type=1）。
 * 例：某台手机的"屏幕=6.7英寸"。一个商品一个属性只有一个值（uk_product_attr）。
 */
@Data
@TableName("product_attribute_value")
public class ProductAttributeValue {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private Long productId;        // product_id 关联 product.id
    private Long attributeId;      // attribute_id 关联 product_attribute.id(type=1)
    private String value;          // 单值，如：2023 / 6.1英寸
}
