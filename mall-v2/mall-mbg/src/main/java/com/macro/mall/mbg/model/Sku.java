package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("sku")
public class Sku {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private Long productId;        // product_id 关联 product.id
    private String skuCode;        // sku_code 唯一，后端生成（决策①）
    private String spData;         // sp_data 规格数据(JSON)，可空
    private BigDecimal price;      // 单价 decimal(10,2)
    private Integer stock;         // 库存，默认 0
    private Integer lockStock;     // 锁定库存，默认 0
    private String pic;            // 可空
    private Integer sale;          // 销量，默认 0
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
    // ⚠️ 不加 deleteStatus：sku 表无该列 → 物理删除（阶段6 决策）
}
