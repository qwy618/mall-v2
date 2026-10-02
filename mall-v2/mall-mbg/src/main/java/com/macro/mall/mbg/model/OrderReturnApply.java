package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Data
@TableName("order_return_apply")
public class OrderReturnApply {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private Long orderId;          // 关联订单
    private String orderSn;        // 冗余订单号
    private Long memberId;         // 申请人（会员）
    private BigDecimal returnAmount; // 退款金额 = Σ(real_amount × 退数/行数)
    private String reason;         // 退货原因
    private String description;    // 说明
    private String proofPics;      // 凭证图 URL 数组（JSON 字符串）
    private String returnItems;    // 退货明细 JSON：[{orderItemId,skuId,productId,productName,productPic,quantity,realAmount}]
    private Integer status;        // 0待审核 1已同意 2已拒绝 3已收货 4已完成 5已关闭
    private String handleNote;     // 处理备注
    private String handleMan;      // 处理人（管理员用户名）
    private String companyAddress; // 退货收货地址（管理端同意时填）
    private String returnTrackingNo; // 会员回填的退货物流单号
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
