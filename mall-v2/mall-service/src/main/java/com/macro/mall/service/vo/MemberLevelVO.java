package com.macro.mall.service.vo;

import lombok.Data;

/**
 * 会员成长信息（债务18）：当前等级 + 权益 + 成长进度 + 积分余额，供个人中心展示。
 */
@Data
public class MemberLevelVO {
    private Long levelId;
    private String levelName;
    private Integer integrationRate;   // 下单赠送积分倍率(%)
    private Integer discountRate;      // 会员折扣(%)
    private Integer growth;            // 当前成长值
    private Integer integration;       // 当前可用积分
    private Integer historyIntegration;// 累计获得积分

    // 距离下一等级（已是最高等级时 next* 为 null、progress=100）
    private String nextLevelName;
    private Integer nextGrowthPoint;
    private Integer growthGap;         // 还差多少成长值升级
    private Integer progress;          // 当前等级区间进度 0-100
}
