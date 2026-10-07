package com.macro.mall.mbg.dto;

import lombok.Data;

import java.util.List;

/**
 * 一个规格筛选组（P2「按规格筛选」反查入参）。
 *
 * 语义：`attribute_id = ? AND value IN (...)`。
 * attributeId 是**单个**属性——属性名在分类内唯一（uk_category_name），
 * 且规格筛选必须先选分类（面板按分类聚合，「颜色」在全库有 7 个不同 id）。
 *
 * @see com.macro.mall.mbg.mapper.SkuAttributeValueMapper#selectSkuIdsBySpecGroups
 */
@Data
public class SpecQueryGroup {

    /** 规格属性的 id（product_attribute.type=0） */
    private Long attributeId;

    /** 本组选中的取值，同组内 OR（黑色 或 白色） */
    private List<String> values;

    public SpecQueryGroup() {
    }

    public SpecQueryGroup(Long attributeId, List<String> values) {
        this.attributeId = attributeId;
        this.values = values;
    }
}
