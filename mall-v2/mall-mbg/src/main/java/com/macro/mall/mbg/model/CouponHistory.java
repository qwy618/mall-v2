package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import lombok.Data;

import java.io.Serializable;
import java.time.LocalDateTime;

@Data
public class CouponHistory implements Serializable {

    private static final long serialVersionUID = 1L;


    @TableId(value = "id", type = IdType.AUTO)
    private Long id;


    private Long couponId;

    private Long memberId;

    private String couponCode;

    private Long orderId;

    private String orderSn;

    private Integer status;

    private LocalDateTime createTime;

    private LocalDateTime useTime;
}
