package com.macro.mall.portal.dao;

import lombok.Data;

import java.math.BigDecimal;

/**
 * 退货明细 DTO：序列化进 order_return_apply.return_items(JSON)。
 * 金额取 order_item.real_amount（债务7 已落库），退款按实付分摊，杜绝按原价退。
 */
@Data
public class ReturnItemDTO {
    private Long orderItemId;
    private Long skuId;
    private Long productId;
    private String productName;
    private String productPic;
    private Integer quantity;
    private BigDecimal realAmount;

    public ReturnItemDTO() {
    }

    public ReturnItemDTO(Long orderItemId, Long skuId, Long productId,
                         String productName, String productPic, Integer quantity, BigDecimal realAmount) {
        this.orderItemId = orderItemId;
        this.skuId = skuId;
        this.productId = productId;
        this.productName = productName;
        this.productPic = productPic;
        this.quantity = quantity;
        this.realAmount = realAmount;
    }
}
