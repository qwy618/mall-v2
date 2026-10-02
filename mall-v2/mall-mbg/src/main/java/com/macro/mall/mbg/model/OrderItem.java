package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;
//订单快照
@Data
@TableName("order_item")
public class OrderItem {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private Long orderId;       // order_id
    private String orderSn;     // order_sn
    private Long skuId;         // sku_id
    private String skuCode;     // sku_code 快照
    private Long productId;     // product_id
    private String productName; // product_name 快照
    private String productPic;  // product_pic 快照
    private String productSn;   // product_sn 快照
    private String spData;      // sp_data 规格JSON
    private BigDecimal price;   // price 快照(库sku价)
    private Integer quantity;   // quantity 默认1
    private Integer commentStatus; // comment_status 0未评价 1已评价（评价系统冗余标记，免联表）

    // ===== 债务7：优惠分摊（退款按 real_amount 退，防薅羊毛）=====
    private BigDecimal couponAmount;       // 本行分摊的优惠券金额
    private BigDecimal promotionAmount;    // 本行分摊的促销/满减金额
    private BigDecimal integrationAmount;  // 本行分摊的积分抵扣金额
    private BigDecimal realAmount;         // 本行实际实付 = price*qty - 各项分摊
    private LocalDateTime createTime;
}
