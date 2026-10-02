package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("orders")
public class Order {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private Long couponId;
    private BigDecimal couponAmount;
    // ===== 债务6/18：会员折扣 + 积分抵扣（DDL 010）=====
    private BigDecimal promotionAmount;   // promotion_amount 会员等级折扣金额
    private Integer useIntegration;       // use_integration 使用的积分数
    private BigDecimal integrationAmount; // integration_amount 积分抵扣金额（100 积分 = 1 元）
    private String orderSn;          // order_sn (UNIQUE) 后端生成，普通字段
    private String submitToken;      // submit_token (UNIQUE) 下单幂等令牌（债务23），历史订单为 NULL
    private Long memberId;          // member_id
    private Long addressId;         // address_id
    private BigDecimal totalAmount; // total_amount
    private BigDecimal payAmount;   // pay_amount
    private BigDecimal freightAmount;// freight_amount 默认0
    private Integer payType;        // pay_type 默认0，模拟支付可空
    private Integer status;         // status 默认0，订单状态机
    private String deliveryCompany; // delivery_company 发货填
    private String deliverySn;      // delivery_sn 发货填
    private Integer deleteStatus;   // ⚠️ delete_status 必须加！走全局逻辑删
    private String receiverName;    // 地址快照↓
    private String receiverPhone;
    private String receiverProvince;
    private String receiverCity;
    private String receiverDistrict;
    private String receiverDetailAddress;
    private LocalDateTime createTime;     // DB 默认，禁 set
    private LocalDateTime paymentTime;    // 支付时后端填
    private LocalDateTime deliveryTime;   // 发货时填
    private LocalDateTime receiveTime;    // 确认收货填
    private LocalDateTime closeTime;      // 取消时填
    private LocalDateTime updateTime;     // DB on update，禁 set
}
