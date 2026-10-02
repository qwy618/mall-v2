package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("order_operate_history")
public class OrderOperateHistory {
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    private Long orderId;          // 关联订单
    private String orderSn;        // 冗余订单号
    private String operateMan;     // 操作人：会员端=会员{memberId}，管理端=管理员用户名
    private String operateType;    // CREATE/PAY/CANCEL/SHIP/CONFIRM/RETURN_APPLY/RETURN_APPROVE/RETURN_REJECT/RETURN_RECEIVE/RETURN_COMPLETE
    private String operateNote;    // 备注（如发货公司+单号）
    private LocalDateTime createTime;
}
