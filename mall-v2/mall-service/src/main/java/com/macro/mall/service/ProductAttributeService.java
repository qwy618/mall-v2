package com.macro.mall.service;

import com.macro.mall.mbg.model.ProductAttribute;
import com.macro.mall.service.vo.AttributeItemVO;
import com.macro.mall.service.vo.SpecOptionVO;

import java.util.List;

/**
 * 商品属性服务（债务 1）—— 跨端统一口径，放在 mall-service 供 admin 与 portal 共用。
 *
 * 两种属性，粒度不同，不可混存：
 *   · 规格 type=0：SKU 级，影响价格与库存（颜色 / 容量），存 sku_attribute_value
 *   · 参数 type=1：商品级，仅展示（屏幕尺寸 / 上市年份），存 product_attribute_value
 *
 * 真源仍是 sku.sp_data；sku_attribute_value 是它的派生索引，由 {@link #syncSkuSpecs} 同步。
 */
public interface ProductAttributeService {

    // ==================== 写：SKU 规格同步（admin 调用） ====================

    /**
     * 按 sp_data 重建某个 SKU 的规格值（事务内 delete + insert，天然幂等）。
     * sp_data 为空/非法时只做清空，不报错——SKU 保存不能因此失败。
     * 属性定义查不到会自动建（按 商品的分类 + 属性名），所以存量数据无需人工配属性。
     *
     * @param skuId  SKU 主键
     * @param spData 规格 JSON 原文，如 [{"key":"颜色","value":"黑色"}]
     */
    void syncSkuSpecs(Long skuId, String spData);

    /** SKU 删除时清掉其规格值（sku 是物理删除，这里必须手动清，否则留孤儿行） */
    void removeSkuSpecs(Long skuId);

    // ==================== 写：商品参数（admin 调用） ====================

    /**
     * 覆盖式保存某商品的参数（先清后插）。只接受 type=1 的属性定义；
     * 值为空的项直接跳过（前端表单留空即视为不填）。
     */
    void saveProductParams(Long productId, List<AttributeItemVO> items);

    // ==================== 读：属性定义 ====================

    /** 按分类取属性定义，type 传 null 表示不过滤。按 sort、id 排序 */
    List<ProductAttribute> listDefinitions(Long categoryId, Integer type);

    /** 按商品取属性定义（内部解析 product.category_id），供管理端 SKU 表单/参数表单用 */
    List<ProductAttribute> listDefinitionsByProduct(Long productId, Integer type);

    // ==================== 读：属性值 ====================

    /** 某商品的参数列表（type=1，含属性名，按属性 sort 排序） */
    List<AttributeItemVO> listProductParams(Long productId);

    /** 某商品的规格选项：按属性名分组的可选值（取自该商品各 SKU 的既有取值） */
    List<SpecOptionVO> listSpecOptions(Long productId);
}
