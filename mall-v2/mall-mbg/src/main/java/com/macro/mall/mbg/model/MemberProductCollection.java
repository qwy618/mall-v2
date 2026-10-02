package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("member_product_collection")
public class MemberProductCollection {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private Long memberId;
    private Long productId;
    private String productName;
    private String productPic;
    private BigDecimal productPrice;
    private LocalDateTime createTime;
}
