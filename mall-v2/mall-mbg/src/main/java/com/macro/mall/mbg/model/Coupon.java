package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("coupon")
public class Coupon implements Serializable {

    private static final long serialVersionUID = 1L;


    @TableId(value = "id", type = IdType.AUTO)
    private Long id;


    private String name;


    private BigDecimal amount;


    private BigDecimal minPoint;


    private Integer useType;


    private Long categoryId;


    private Long productId;

    private Integer perLimit;


    private Integer publishCount;


    private Integer receiveCount;

    private Integer useCount;


    private LocalDateTime startTime;


    private LocalDateTime endTime;


    private String note;


    private LocalDateTime createTime;

    private Integer deleteStatus;
}
