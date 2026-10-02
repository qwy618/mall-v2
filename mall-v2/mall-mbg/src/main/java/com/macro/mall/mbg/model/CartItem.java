package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 购物车条目，对应 cart_item 表。
 * 唯一索引 uk_member_sku(member_id, sku_id)：同一会员同一 SKU 只保留一行，
 * 业务层 add 时"已存在则 quantity 累加"。
 * 注意：不设 deleteStatus 列 → 走物理删除（同 sku 规则）。
 */
@Data
@TableName("cart_item")
public class CartItem {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private Long memberId;       // member_id 会员ID
    private Long skuId;          // sku_id SKU ID
    // ===== 快照字段（债务16-快照：商品下架/删除后购物车项仍可灰显保留）=====
    private Long productId;      // product_id 商品ID（快照）
    private String productName;  // product_name 商品名（快照）
    private String skuCode;      // sku_code SKU编码（快照）
    private String pic;          // pic 商品图（快照）
    private String spData;       // sp_data 规格JSON（快照，展示用）
    private java.math.BigDecimal price; // price 加入时快照单价（下架/缺货兜底展示）
    private Integer quantity;    // quantity 购买数量，默认 1，>=1
    private Integer checked;     // checked 是否选中 1选中 0未选，默认 1
    private LocalDateTime createTime; // 库默认 CURRENT_TIMESTAMP，实体不手动 set
}
