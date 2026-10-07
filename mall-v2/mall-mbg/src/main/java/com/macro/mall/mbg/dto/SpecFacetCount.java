package com.macro.mall.mbg.dto;

import lombok.Data;

/**
 * 筛选面板（facet）的一次聚合结果：某规格属性的某个取值命中了多少个商品。
 *
 * = group by attribute_id, value 的一行，product_count 是 **DISTINCT 商品数**
 * （同一商品有多个 SKU 命中同一取值时只算一次）。
 */
@Data
public class SpecFacetCount {

    private Long attributeId;

    private String value;

    /** 命中该取值的已上架商品数 */
    private Integer productCount;
}
