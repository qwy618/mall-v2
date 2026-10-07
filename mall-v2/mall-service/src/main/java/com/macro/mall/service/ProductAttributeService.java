package com.macro.mall.service;

import com.macro.mall.mbg.model.ProductAttribute;
import com.macro.mall.service.vo.AttributeItemVO;
import com.macro.mall.service.vo.SpecFacetVO;
import com.macro.mall.service.vo.SpecMatchVO;
import com.macro.mall.service.vo.SpecOptionVO;

import java.util.List;
import java.util.Map;

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

    // ==================== 读：按规格筛选（P2，债务 2 的顺承） ====================

    /**
     * 反查：找出拥有「满足全部规格条件的 SKU」的商品，并给出这些 SKU 的最低价。
     *
     * <p>语义：**跨属性 AND**（黑色 且 256GB）、**同属性多值 OR**（黑色 或 白色）。
     *
     * <p>为什么只能反查 SKU：{@code product_attribute_value} 是商品级的、还可能是逗号分隔多值，
     * 它只能回答「这个商品有黑色」，回答不了「这个商品有黑色+256G 这个能买的组合」——
     * 后者必须有 SKU 级的 {@code sku_attribute_value} 才能做交叉判断。
     *
     * @param categoryId 分类 id，**必传**。属性按分类隔离（「颜色」在全库有 7 个不同 attribute_id），
     *                   不传分类无法唯一解析属性名 —— 直接返回空结果，与 {@link #listSpecFacets} 的口径一致。
     * @param specs      属性名 → 选中值。分隔符由调用方解析（本方法只认结构化入参）；
     *                   重复的属性名会**自动合并**为一组（否则 HAVING 的阈值会对不上，静默返回空）
     * @return 命中商品 id + 按命中 SKU 算的最低价；任一属性名对不上就是空结果（不是异常）
     */
    SpecMatchVO matchProductsBySpecs(Long categoryId, Map<String, List<String>> specs);

    /**
     * 筛选面板（facet）：某分类下「规格属性 → 可选值 → 命中已上架商品数」。
     *
     * <p>只返回 type=0（规格）的属性；商品数为 0 的取值不返回；
     * 某个属性一个值都没有时整个属性不返回 —— 前端据此渲染「点了必然有货」的面板。
     * count 是本分类下的静态统计，不随已勾选项收敛（动态 facet 见设计文档 §8.5）。
     *
     * @param categoryId 分类 id；为 null 或无规格属性时返回空列表
     */
    List<SpecFacetVO> listSpecFacets(Long categoryId);
}
