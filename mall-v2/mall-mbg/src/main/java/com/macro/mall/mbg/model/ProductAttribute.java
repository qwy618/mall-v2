package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 商品属性定义：某个分类下有哪些属性名（债务 1）。
 * 属性按 category_id 隔离——"颜色/容量"属手机数码、"尺寸/风格"属服装，
 * 不做分类隔离会退化成全局属性池（T恤编辑页冒出"容量"）。
 */
@Data
@TableName("product_attribute")
public class ProductAttribute {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private Long categoryId;       // category_id 归属分类，关联 category.id；同分类下 name 唯一
    private String name;           // 属性名，如：颜色 / 容量 / 尺寸
    private Integer type;          // 0规格(影响价格库存) 1参数(仅展示)
    private Integer inputType;     // 0手工录入 1从列表选择
    private String inputList;      // type=0 时的可选值清单，逗号分隔（管理端下拉用）
    private Integer sort;
    private LocalDateTime createTime;

    // ===== type 取值（避免各层各写魔法数字）=====
    public static final int TYPE_SPEC = 0;   // 规格：SKU 级，存 sku_attribute_value
    public static final int TYPE_PARAM = 1;  // 参数：商品级，存 product_attribute_value
}
