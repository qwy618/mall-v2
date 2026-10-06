package com.macro.mall.portal.vo;

import com.macro.mall.mbg.model.Sku;
import com.macro.mall.service.vo.AttributeItemVO;
import com.macro.mall.service.vo.SpecOptionVO;
import lombok.Data;

import java.util.List;

/**
 * 商品详情。SPU 本身不存售价，售价在 SKU 表，所以这里同时带出 SKU 列表。
 */
@Data
public class ProductDetailVO {
    private ProductVO product;
    private List<Sku> skus;
    /**
     * 商品参数（商品级、仅展示、不影响价格库存），来自 product_attribute_value。
     * 债务1 之前这类信息无处可放，只能硬塞进 sub_title。无数据时是空列表。
     */
    private List<AttributeItemVO> attributes;
    /**
     * 规格选项：按属性名分组的可选值（如 颜色→[黑,白]），来自 sku_attribute_value。
     * 供详情页展示可选规格，也是 P2「按规格筛选」的现成数据源。
     */
    private List<SpecOptionVO> specOptions;
}
