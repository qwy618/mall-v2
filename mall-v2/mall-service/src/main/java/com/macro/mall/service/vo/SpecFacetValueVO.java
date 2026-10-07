package com.macro.mall.service.vo;

import lombok.Data;

/**
 * 筛选面板里的一个可选规格值（P2）。
 * 对应前端 `SpecFilterValue`：{ value, count }。
 */
@Data
public class SpecFacetValueVO {

    /** 规格取值，如「黑色」 */
    private String value;

    /**
     * 命中该取值的**已上架**商品数（DISTINCT）。
     * 只用于面板展示，不参与筛选 —— 是本分类下的静态统计，不随已勾选项收敛
     * （动态 facet 见 docs/商品域属性表设计.md §8.5）。
     */
    private Integer count;
}
