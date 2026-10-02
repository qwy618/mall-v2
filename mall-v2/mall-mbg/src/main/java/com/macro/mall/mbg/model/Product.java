package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("product")
public class Product {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private String productSn;      // product_sn  唯一，后端生成（决策①）
    private String name;           // NOT NULL
    private String subTitle;       // sub_title   可空
    private String pic;            // 可空
    private Long brandId;          // brand_id    关联 brand.id
    private Long categoryId;       // category_id 关联 category.id
    private Integer sale;          // 默认 0
    private Integer status;        // 默认 1（上架）
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
    // ⚠️ 不加 deleteStatus：product 表无该列 → 物理删除（阶段6 决策）
}
