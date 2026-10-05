package com.macro.mall.portal.vo;

import com.macro.mall.mbg.model.MemberAddress;
import lombok.Data;

import java.math.BigDecimal;
import java.util.List;

/**
 * 订单试算结果（债务：金额同源）。
 *
 * <p>本 VO 的每个金额字段都由 {@code OrderServiceImpl.computeAmounts(...)} 产出——
 * 那是最终下单 {@code /order/create} 使用的**同一段代码**。因此确认卡片上展示的金额
 * 与用户实际下单扣款逐分一致，杜绝"看到 5999、扣了 5899"的金额纠纷。
 *
 * <p>与下单的差异仅三点：不扣库存、不落库、不消耗幂等令牌。
 */
@Data
public class OrderPreviewVO {

    /** 收货地址（显式传入则为其本身，未传则为默认地址；无地址时为 null） */
    private MemberAddress address;

    /** 逐行明细（含规格 JSON 与分摊后的实付） */
    private List<PreviewItem> items;

    /** 商品总额 */
    private BigDecimal totalAmount;
    /** 运费（当前固定 0） */
    private BigDecimal freightAmount;
    /** 会员等级折扣金额 */
    private BigDecimal promotionAmount;
    /** 优惠券抵扣金额 */
    private BigDecimal couponAmount;
    /** 积分抵扣金额 */
    private BigDecimal integrationAmount;
    /** 实际使用的积分数 */
    private Integer useIntegration;
    /** 应付金额（= total + freight − promotion − coupon − integration） */
    private BigDecimal payAmount;

    /** 会员等级名（如「金卡」），无等级配置时为 null */
    private String levelName;
    /** 会员折扣率（%）：100 = 原价 */
    private Integer discountRate;

    /** 试算行明细：金额分摊算法与下单同源 */
    @Data
    public static class PreviewItem {
        private Long skuId;
        private Long productId;
        private String productName;
        /** 取图口径与购物车/订单一致：优先 SKU 图，无图回退 SPU 商品图 */
        private String productPic;
        /** 规格 JSON（sp_data），前端用 utils/spec.formatSpec 展示 */
        private String spData;
        /** 单价快照 */
        private BigDecimal price;
        private Integer quantity;
        /** 本行原价小计 = price × quantity */
        private BigDecimal lineAmount;
        /** 本行分摊的会员折扣 */
        private BigDecimal promotionAmount;
        /** 本行分摊的优惠券 */
        private BigDecimal couponAmount;
        /** 本行分摊的积分抵扣 */
        private BigDecimal integrationAmount;
        /** 本行分摊后实付 = lineAmount − 三项分摊 */
        private BigDecimal realAmount;
    }
}
