package com.macro.mall.service.vo;

import lombok.Data;

import java.util.List;

/**
 * 筛选面板里的一个规格属性（P2）。
 * 对应前端 `SpecFilterGroup`：{ attributeId, name, values: [{ value, count }] }。
 *
 * 只包含 type=0（规格）的属性 —— 参数（type=1）是商品级、不影响价格库存，无法用于筛选。
 */
@Data
public class SpecFacetVO {

    private Long attributeId;

    /** 属性名，如「颜色」 */
    private String name;

    /** 可选值（已按命中商品数倒序；商品数为 0 的值不会出现） */
    private List<SpecFacetValueVO> values;
}
