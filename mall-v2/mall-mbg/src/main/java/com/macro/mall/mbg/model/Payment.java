package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.io.Serializable;
import java.math.BigDecimal;
import java.util.Date;

/**
 * 支付流水
 * 对应表 payment
 */
@Data
@TableName("payment")
public class Payment implements Serializable {

    private static final long serialVersionUID = 1L;

    /** 主键 */
    @TableId(type = IdType.AUTO)
    private Long id;

    /** 关联订单ID */
    private Long orderId;

    /** 订单编号（冗余，便于对账） */
    private String orderSn;

    /** 支付用户ID */
    private Long memberId;

    /** 支付金额（=订单 pay_amount，后端权威） */
    private BigDecimal amount;

    /** 退款金额（订单作废时写入） */
    private BigDecimal refundAmount;

    /** 支付方式 1=mock模拟 2=微信 3=支付宝 */
    private Integer payType;

    /** 支付状态 0=未支付 1=已支付 2=已退款 */
    private Integer status;

    /** 支付完成时间 */
    private Date payTime;

    /** 退款时间 */
    private Date refundTime;

    /** 创建时间 */
    private Date createTime;
}