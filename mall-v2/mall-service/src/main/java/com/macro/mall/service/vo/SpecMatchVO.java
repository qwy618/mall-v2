package com.macro.mall.service.vo;

import lombok.Data;

import java.math.BigDecimal;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * 「按规格筛选」的反查结果（P2）。
 *
 * <p>两个字段是一体的，缺一不可：
 * <ul>
 *   <li>{@code productIds} —— 命中**全部**规格条件的商品 id（DISTINCT）。
 *       调用方拿它作为 `in` 条件去做常规分页，这样 total 天然等于
 *       「再叠加分类/品牌/上架过滤后的商品数」，不必手拼 Page（很容易算错）。</li>
 *   <li>{@code minPriceByProduct} —— 商品 id → **满足全部规格条件的那些 SKU** 的最低价。
 *       注意不是「商品全局最低价」：筛「容量=256G」时若仍显示 128G 的价格，
 *       列表写「¥2999 起」、点进去 256G 却要 ¥3499，用户会觉得被骗。</li>
 * </ul>
 */
@Data
public class SpecMatchVO {

    private List<Long> productIds;

    private Map<Long, BigDecimal> minPriceByProduct;

    public SpecMatchVO() {
    }

    public SpecMatchVO(List<Long> productIds, Map<Long, BigDecimal> minPriceByProduct) {
        this.productIds = productIds;
        this.minPriceByProduct = minPriceByProduct;
    }

    /** 无命中（属性名对不上 / 值不存在 / 未传分类）时的统一空结果 */
    public static SpecMatchVO empty() {
        return new SpecMatchVO(Collections.emptyList(), Collections.emptyMap());
    }
}
