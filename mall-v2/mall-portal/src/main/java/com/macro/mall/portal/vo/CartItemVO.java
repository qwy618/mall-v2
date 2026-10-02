package com.macro.mall.portal.vo;

import lombok.Data;
import java.math.BigDecimal;

@Data
public class CartItemVO {
    private Long cartItemId;
    private Long skuId;
    private Long productId;     // 商品ID（快照）
    private String skuCode;
    private String productName;
    private String pic;
    private String spData;      // 规格JSON（快照，展示用）
    private BigDecimal price;   // 实时单价（下架时回退快照价）；前端只展示，下单以库为准
    private Integer stock;      // 库的实时库存
    private Integer quantity;
    private Integer checked;    // 1选中 0未选
    private Boolean offline;    // true=商品已下架/失效，前端灰显且不可结算
}
