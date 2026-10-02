package com.macro.mall.mbg.model;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 会员积分流水（债务18，DDL 010 落库）。
 * change_type：1 下单赠送 / 2 下单抵扣 / 3 退货扣回 / 4 管理员调整。
 * change_count 正=获得、负=消耗；integration_after 为变动后余额，便于对账。
 */
@Data
@TableName("member_integration_history")
public class MemberIntegrationHistory {
    @TableId(type = IdType.AUTO)
    private Long id;
    private Long memberId;
    private Long orderId;           // 关联订单（下单抵扣 / 订单赠送 / 退货扣回）
    private String orderSn;         // 订单号冗余，免联表
    private Integer changeType;     // 1下单赠送 2下单抵扣 3退货扣回 4管理员调整
    private Integer changeCount;    // 变动值：正=获得 负=消耗
    private Integer integrationAfter;// 变动后可用积分余额
    private String operateMan;      // 会员{id} / system / 管理员用户名
    private String operateNote;
    private LocalDateTime createTime;
}
